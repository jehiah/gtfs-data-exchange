import S3,os,sys
import urllib2,md5
from s3settings import AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY
from feedvalidatortext import main as feedvalidatortext
import popen2
import MultipartPostHandler

class validategtfsfiles:
    def __init__(self):
        from transitfeed import __version__ as transitfeedversion
        print "using transitfeed version", transitfeedversion
        if '--remote' in sys.argv:
            self.homebase = 'http://www.gtfs-data-exchange.com/'
            self.bucket = "gtfs"
        else:
            self.homebase = 'http://localhost:8081/'
            self.bucket = "gtfs-devel"

        auth_handler = urllib2.HTTPBasicAuthHandler()
        auth_handler.add_password(realm='RESTRICTED ACCESS',
                                      uri=self.homebase,
                                      user='crawler',
                                      passwd='crawler')
        self.opener = urllib2.build_opener(auth_handler,MultipartPostHandler.MultipartPostHandler)
        self.opener.addheaders = [('User-agent', 'Mozilla/5.0 crawler http://www.gtfs-data-exchange.com')]
        urllib2.install_opener(self.opener)
        self.reconnect()
    
    def reconnect(self):
        self.conn = S3.AWSAuthConnection(AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY)


    def getItems(self):
        while True:
            f = urllib2.urlopen(self.homebase + 'ValidationResults').read()
            if f.startswith('FILE:'):
                yield f.replace('FILE:','')
            else:
                return
        # for x in self.conn.list_bucket(self.bucket).entries:
        #     if not x.key.startswith('queue'):
        #         yield x.key

    def run(self):
        if '-f' in sys.argv:
            filename = sys.argv[sys.argv.index('-f')+1]
            return self.handleItem(filename)
        for x in self.getItems():
            self.handleItem(x)

    def getfile(self,filename):
        if os.access('/tmp/gtfs/'+filename,os.R_OK):
            return False
        print "saving",filename,"to /tmp/gtfs"
        obj = self.conn.get(self.bucket,filename).object
        f = open('/tmp/gtfs/'+filename,'wb')
        f.write(obj.data)
        f.close()
    
    def uncompress(self,filename):
        target = '/tmp/gtfs/'+filename.replace('.zip','')
        if os.access(target,os.R_OK):
            return
        print "unzipping %s" % filename
        os.mkdir(target)
        pipe = popen2.Popen4('cd %s && unzip ../%s' % (target,filename))
        pipe.wait()
        
    def validate(self,filename):
        target = '/tmp/gtfs/'+filename.replace('.zip','')
        print "validating", target
        try:
            return feedvalidatortext(target)
        except:
            print sys.exc_info()[0],sys.exc_info()[1]
            return '<p><strong>Error: An unknown error occured during feed validation. </strong> Unable to validate.</p>'
    
    def handleItem(self,filename):
        if os.access('/tmp/gtfs/'+filename + '.skip',os.R_OK):
            print "skip file found for ",filename
            self.save(filename,' ')
            return
        
        self.getfile(filename)
        # if self.getfile(filename) == False:
        #     ## temporarily skip previously downloaded files
        #     return
        self.uncompress(filename)
        output = self.validate(filename)
        if output.find('<tr><th>Agencies:</th><td>0</td></tr>') != -1:
            print output
            #raise Exception("validation failed, try removing the zip file and re-validating")
            output= '<p><strong>Error: An unknown error occured during feed validation. </strong> Unable to validate.</p>'
            
        self.save(filename,output)

    def save(self,filename,results):
        print "results are",results
        md5sum = md5.md5(open('/tmp/gtfs/'+filename,'rb').read()).hexdigest()
        print "md5",md5sum
        req = urllib2.Request(self.homebase+'ValidationResults')
        req.add_data({'filename': filename,
                      'results':results,
                      'md5sum':md5sum})
        print urllib2.urlopen(req).read()
        

if __name__ == "__main__":
    validategtfsfiles().run()
        