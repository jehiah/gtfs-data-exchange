import base64
import datetime
import glob
import md5
import os
import re
import sys
import random
import string
import subprocess
import time
import traceback
import urllib
import urllib2

import BeautifulSoup
import MultipartPostHandler
import S3
from s3settings import AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY

DEBUG = False

if DEBUG:
    import logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)-8s %(filename)s %(lineno)d %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        filename='app.log',
                        filemode='aw')
    log = logging.getLogger()

random.seed()

class StopNow(Exception):
    pass

class DownloadError(Exception):
    pass

class Crawler:
    def __init__(self):
        if '--remote' in sys.argv:
            self.bucket = 'gtfs'
            self.homebase = 'http://www.gtfs-data-exchange.com/'
        else:
            self.bucket = 'gtfs-devel'
            self.homebase = 'http://localhost:8085/'

        auth_handler = urllib2.HTTPBasicAuthHandler()
        auth_handler.add_password(realm='RESTRICTED ACCESS',
                                      uri=self.homebase,
                                      user='crawler',
                                      passwd='crawler')
        self.opener = urllib2.build_opener(auth_handler,MultipartPostHandler.MultipartPostHandler)
        self.opener.addheaders = [('User-agent', 'Mozilla/5.0 crawler http://www.gtfs-data-exchange.com/')]
        urllib2.install_opener(self.opener)
        self.seenlinks = []
        self.conn = S3.AWSAuthConnection(AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY)
        self.totalsleep = 0.0
        self.starttime = time.time()
        self.totalurls = 0
        self.total304 = 0
        self.totaldownload = 0
        self.errorurls = 0
        self.exit = False

    def isSpecialUrl(self,url):
        return {'http://www2.septa.org/developer':'septa'}.get(url,None)
    
    def getNextCrawlUrl(self):
        if '--shunt' in sys.argv:
            if self.exit:
                raise StopNow()
            self.exit = True
            settings= {'recurse':1,'download_as':'gtfs-archiver','show_url':True,'post_text':''}
            url = sys.argv[sys.argv.index('--shunt')+1]
            if not url.startswith('http://') and not url.startswith('ftp://'):
                print "invalid shunt url",url
                raise StopNow()
            settings['url']=url
            return settings['url'],settings
            
        f = urllib2.urlopen(self.homebase+'crawl/nexturl').read()
        if f == 'NONE' or not f.startswith('{'):
            raise StopNow()
        settings = eval(f)
        print '<=',settings['url']
        return settings['url'],settings
    
    def headers(self,url):
        if '--no-304' in sys.argv:
            return None
        f = urllib2.urlopen(self.homebase+'crawl/headers?'+urllib.urlencode({'url': url})).read()
        if not f or f == 'NONE':
            return None
        return eval('('+f+')')
        
    def saveheaders(self,url,headers):
        if '--dont-save-headers' in sys.argv:
            return
        if '--shunt' in sys.argv:
            return
        ## Last-Modified -> If-Modified-Since
        d = {}
        if headers.get('Last-Modified',None):
            headers['If-Modified-Since'] = headers.get('Last-Modified',None)
        for k in ['If-Modified-Since','Etag']:
            if headers.get(k,None):
                d[k]=headers[k]
        
        req = urllib2.Request(self.homebase+'crawl/headers')
        req.add_data({'url': url,'headers':str(d)})
        urllib2.urlopen(req).read()
    
    def crawlSpecial(self,url,settings):
        agency = self.isSpecialUrl(url)
        if agency != 'septa':
            return
        url = 'http://www2.septa.org/developer/download.php?fc=septa_gtfs.zip&download=download'
        localdir = '/tmp/gtfs/ftpmirror/%s' % agency

        print "crawling",url
        
        if not os.path.exists(localdir):
            os.mkdir(localdir)

        for filename in ('gtfs_data.zip','google_rail.zip','google_bus.zip'):
            if os.path.exists('%s/%s' % (localdir,filename)):
                print "removing old %s/%s" % (localdir,filename)
                os.unlink('%s/%s' % (localdir,filename))
        
        zipdata = self.getUrl(url,None)
        f = open('%s/gtfs_data.zip'%localdir,'wb')
        f.write(zipdata)
        f.close()
        self.totaldownload +=1
        
        cmd = 'unzip "%s/gtfs_data.zip" -d "%s"' % (localdir,localdir)
        pipe = subprocess.Popen(cmd, close_fds=True, stdout=subprocess.PIPE, shell=True)
        print pipe.stdout.read()
        
        os.unlink('%s/gtfs_data.zip' % localdir)
        print "removing %s/gtfs_data.zip" % localdir
        
        ## unzip
        self.crawlLocalDir(localdir,settings,"septa:")
            
    
    def crawlFtp(self, url, settings):
        ## parse the url
        ## run ftpmirror.py
        ## get the zip files and check the md5's
        pattern = re.compile('ftp://(?P<username>.*):(?P<password>.*)@(?P<hostname>.*?)/(?P<path>.*)')
        m = pattern.match(url)
        if m:
            g = m.groupdict()
            print g
            username = g['username']
            password = g['password']
            hostname = g['hostname']
            fullpath = g['path']
        else:
            pattern = re.compile('ftp://(?P<hostname>.*?)/(?P<path>.*)')
            m = pattern.match(url)
            if not m:
                print "** no ftp match",url
                return
            g = m.groupdict()
            print g
            username = 'anonymous'
            password = ''
            hostname = g['hostname']
            fullpath = g['path']
            
        if fullpath.endswith('.zip'):
            path = '/'.join(fullpath.split('/')[:-1])
            filename = fullpath.split('/')[-1]
        else:
            path = fullpath
            filename = None
        
        if not os.path.exists('/tmp/gtfs/ftpmirror/'):
            os.mkdir('/tmp/gtfs/ftpmirror/')
        localdir = "/tmp/gtfs/ftpmirror/%s" % hostname
        if not os.path.exists(localdir):
            os.mkdir(localdir)
        scriptpath = '/'.join(__file__.split('/')[:-1])
        command = 'python %s/ftpmirror.py -v -r -l "%s" -p "%s" %s "%s" "%s"' % (scriptpath, username, password, hostname, path, localdir)
        print ">> running",command
        p = subprocess.Popen(command, stdout=subprocess.PIPE, close_fds=True, shell=True)
        print p.stdout.read()
        del p
        print '>> done ftpmirror.py'
        self.crawlLocalDir(localdir, settings, 'ftp://%s' % hostname, localfile=None)
        
    def isAlreadyUploaded(self, md5sum):    
        req = urllib2.Request(self.homebase+'crawl/upload?'+urllib.urlencode({'md5sum': md5sum}))
        post = urllib2.urlopen(req)
        upload_result = post.read()
        return upload_result.startswith('FOUND')
    
    def getNextUploadKey(self):
        randstring = ''.join([random.choice(string.letters+string.digits) for x in range(20)])
        return 'queue/'+str(datetime.datetime.now())+'-'+randstring+'.zip'
        
    def crawlLocalDir(self, localdir, settings, desc, localfile=None):
        ## now find the files
        if localfile:
            files = glob.glob(localdir + '/' + localfile)
        else:
            files = glob.glob(localdir+'/*.zip') +  glob.glob(localdir+'/*/*.zip') + glob.glob(localdir+'/*/*/*.zip')
        for filename in files:
            shortname = filename.replace(localdir+'/','')
            
            d = open(filename,'rb').read()
            md5sum = md5.md5(d).hexdigest()
            if self.isAlreadyUploaded(md5sum):
                # note, we could save this file to our meta folder
                print "already uploaded %s/%s" % (desc,shortname)
                continue
            
            nextkey = self.getNextUploadKey()
            if '--shunt' in sys.argv and '--allow-upload' not in sys.argv:
                print "<fake> uploading %s/%s" % (desc,shortname),nextkey
                continue

            o = S3.S3Object(d)
            o.metadata['user']=settings['download_as'] + '@gmail.com'
            o.metadata['gtfs_crawler']='t'
            o.metadata['comments'] = settings.get('post_text','') % {'filename':shortname}
            self.conn.put(self.bucket,nextkey,o)
            print "==> uploaded %s/%s" % (desc,shortname),'as',nextkey
        
    def shouldSkipUrl(self,url):
        ## check the server to see if it's skipped there
        req = urllib2.Request(self.homebase+'crawl/shouldSkip?'+urllib.urlencode({'url': url}))
        post = urllib2.urlopen(req)
        result = post.read()
        if result.startswith('YES'):
            return True
    
    def getUrl(self,url,referer):
        ## fetch previous request headers
        pattern = re.compile('http://(?P<username>.*):(?P<password>.*)@(?P<domain>.*?)/(?P<path>.*)')
        headers = self.headers(url) or {}
        m = pattern.match(url)
        if m:
            g = m.groupdict()
            raw = "%s:%s" % (g['username'], g['password'])
            print "raw Authorization:", raw
            url = "http://%s/%s" % (g['domain'], g['path'])
            headers = self.headers(url) or {}

            if raw == "kcwww\\tr_pub_user:S6dffr$b":
                ## special case to use NTCL 
                headers['WWW-Authenticate'] = "NTLM TlRMTVNTUAACAAAACgAKADgAAAAFgokC0EdrnBZZhPUAAAAAAAAAAHgAeABCAAAABQLODgAAAA9LAEMAVwBXAFcAAgAKAEsAQwBXAFcAVwABABgAUABPADgAVwAxAEIASQBNAFQANgBYAFIABAAMAGsAYwAuAHcAdwB3AAMAJgBwAG8AOAB3ADEAYgBpAG0AdAA2AHgAcgAuAGsAYwAuAHcAdwB3AAUADABrAGMALgB3AHcAdwAAAAAA"
                print "WWW-Authenticate:", headers['WWW-Authenticate']
            else:
                headers['Authorization'] = 'Basic %s' % base64.b64encode(raw).strip()
                print "Authorization:", headers['Authorization']

        if referer:
            headers['Referer']=referer
        ## get url
        self.totalurls +=1
        req = urllib2.Request(url)
        for h,v in headers.items():
            req.add_header(h, v)

        try:
            r = urllib2.urlopen(req)
            i = r.info()
            d = r.read()
        except urllib2.HTTPError, e:
            if e.code ==304:
                print " \==>304"
                self.total304 +=1
                self.saveheaders(url,e.headers)
                raise DownloadError()
            elif e.code == 110:
                print "** connection refused on",url
                self.errorurls+=1
                raise DownloadError()
            else:
                print "** got error ",e.code,"on",url
                self.errorurls+=1
                raise DownloadError()
        except urllib2.URLError, e:
            print "*** got url error",e
            self.errorurls +=1
            traceback.print_tb(sys.exc_info()[2])
            raise DownloadError()

        self.saveheaders(url,i)
        return d
    
    def crawl(self,url,settings,referer=None):
        if url in self.seenlinks:
            # print "skipping seen link"
            return
        self.seenlinks.append(url)
        if url.startswith('ftp://'):
            return self.crawlFtp(url,settings)
        if self.isSpecialUrl(url):
            return self.crawlSpecial(url,settings)

        print "-+",url,"recurse:",settings['recurse']
        
        ## check for server side skipped urls
        if self.shouldSkipUrl(url):
            print '\==[skipped by server]'
            return
        
        try:
            d = self.getUrl(url,referer)
        except DownloadError, e:
            return
        except:
            print "** unknown exception on",url
            traceback.print_tb(sys.exc_info()[2])
            self.errorurls+=1
            return
            
        settings['recurse'] -=1

        if url.endswith(".pdf"):
            print "\==pdf <skipped>"
            return
        if url.endswith(".zip"):
            self.totaldownload +=1
            
            ## check if the md5 already exists
            md5sum = md5.md5(d).hexdigest()
            if self.isAlreadyUploaded(md5sum):
                print 'already uploaded',url
                return
            
            nextkey = self.getNextUploadKey()
            
            if '--shunt' in sys.argv and '--allow-upload' not in sys.argv:
                print '<fake> uploading as',nextkey
                return
            
            o = S3.S3Object(d)
            o.metadata['user']=settings['download_as'] + '@gmail.com'
            o.metadata['gtfs_crawler']='t'
            if settings['show_url']:
                o.metadata['comments']='Archived from %s' % url
            else:
                o.metadata['comments']=''
            if settings['post_text']:
                o.metadata['comments'] += settings['post_text']
            self.conn.put(self.bucket,nextkey,o)
            print "==> uploaded",url,'as',nextkey
            return

        ## find links
        try:
            soup = BeautifulSoup.BeautifulSoup(d)
            for a in soup.findAll('a'):
                h = a['href']
                t = h

                # print "found link",a," href",h," in ",url
            
                if h.find('?') != -1:
                    #print "skipping because link has parameters",h
                    continue

                if h.startswith('/'):
                    ## absolute link w/o domain
                    b= url[:url.find('/',9)]
                    t = b + h
                elif not h.startswith('http'):
                    # it's a relative link
                    if url.count('/') >= 3 and not url.endswith('/'):
                        b = '/'.join(url.split('/')[:-1]) + '/'
                    else:
                        b = url ## http://...com/
                    t = b + h
                
                if not t.startswith(settings['url']):
                    # print "skipping",t,"does not start with",base
                    continue
            
                if '_vti_cnf' in t:
                    continue
            
                # print "link is now",t
                # print "sleeping"
                sleeptime = random.random()*3
                self.totalsleep += sleeptime
                time.sleep(sleeptime)
                if h.endswith('.zip'):
                    self.crawl(t,dict(settings),referer=url)
                elif settings['recurse'] >= 0:
                    self.crawl(t,dict(settings),referer=url)
        except:
            self.errorurls+=1
            print "** error parsing page",url,sys.exc_info()[0],sys.exc_info()[1]
                
        
    
        
    def run(self):
        while True:
            try:
                self.crawl(*self.getNextCrawlUrl())
            except StopNow, e:
                print "got stop command"
                break
            except:
                if DEBUG:
                    log.exception('an unknown error happened')
                print 'unknown error',sys.exc_info()[0],sys.exc_info()[1]
                break
            self.totalsleep += 1
            time.sleep(1)
        print 'Total Time for %0.2f seconds %0.2f of which were sleeping' % (time.time()-self.starttime,self.totalsleep)
        print '%d urls (%d 304) (%d downloaded) (%d errors)' % (self.totalurls, self.total304,self.totaldownload,self.errorurls)

    def undoLastRun(self):
        print "undoing last run"
        req = urllib2.Request(self.homebase+'crawl/undoLastRun')
        req.add_data({'_':''})
        print urllib2.urlopen(req).read()

def main():
    c = Crawler()
    print """
    
USAGE: (-h or --help displays this)
    
--no-304 

    to skip getting headers from a previous run to force a re-crawl of everything. 
    this will still allow headers from this run to be saved
    
--dont-save-headers 

    to skip saving headers for a future run
    
--shunt http://example.com/path/ 

    to crawl that url. NOTE: all links will be posted as gtfs-archiver with the url displayed.
    
--remote
    
    to upload to gtfs-data-exchange. exclude it to upload to the dev bucket
    
--undo-last

    to post to crawl/undoLastRun which deletes headers from the last 12 hours, and sets the last crawl on urls -24 hours
    
    """
    if '-h' in sys.argv or '--help' in sys.argv:
        return
    if '--undo-last' in sys.argv:
        c.undoLastRun()
    else:
        c.run()

if __name__ == "__main__":
    main()