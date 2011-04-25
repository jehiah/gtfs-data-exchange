import S3
import os
import sys
import urllib2
import time
import hashlib
import zipfile
import StringIO
import EmailUtils
import tornado.options
import logging

import markdown
import MultipartPostHandler
from s3settings import AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY

class StopNow:
    pass
    
class DeleteKey:
    def __init__(self, key, msg):
        self.key = key
        self.msg = msg


class BackgroundProcessor:
    def __init__(self):
        if tornado.options.options.environment == "dev":
            self.bucket = 'gtfs-devel'
            self.homebase = 'http://localhost:8085/'
        else:
            self.bucket = 'gtfs'
            self.homebase = 'http://www.gtfs-data-exchange.com/'
            self.homebase = 'http://6.gtfs-data-exchange.appspot.com/'

        logging.info('remote endpoint is %s' % self.homebase)

        self.opener = urllib2.build_opener(MultipartPostHandler.MultipartPostHandler)
        self.opener.addheaders = [('User-agent', 'Mozilla/5.0 (gtfs feed crawler http://www.gtfs-data-exchange.com/)')]
        urllib2.install_opener(self.opener)
        self.reconnect()
        self.markdown = markdown.Markdown()
        
    def reconnect(self):
        self.conn = S3.AWSAuthConnection(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)

    def sendSuccessEmail(self, filename, metadata):
        email = metadata.get('user','')
        comments = self.markdown.convert(metadata.get('comments',''))
        if not email:
            logging.warning("error, no email stored %r %r" % (filename, metadata))
            return
        nickname = email.split('@')[0]
        if email == "gtfs-archiver@gmail.com":
            email = "jehiah+gtfsarchiver@gmail.com"
        if metadata.get('gtfs_crawler','f') == 't':
            email = "jehiah+gtfsarchiver@gmail.com"
            
        text = """
Thank you for your participation in sharing 
transit schedule data with others. Open access
to data fosters inovation, and promotes transit
usage.        
        
The file you uploaded is now 
archived on GTFS Data Exchange as    
%(filename)s.

%(comments)s

You can view this file along with your comments at    
<http://www.gtfs-data-exchange.com/user/%(nickname)s/>
""" % {'filename':filename,'nickname':nickname,'comments':comments}
        EmailUtils.sendEmail(email,'GTFS Upload Successful',text)
        if email != "jehiah+gtfsarchiver@gmail.com":
            EmailUtils.sendEmail('jehiah+gtfsarchiver@gmail.com','GTFS File Uploaded','%(filename)s was uploaded by %(nickname)s' % {'filename':filename,'nickname':nickname,'comments':comments})
        

    def sendErrorEmail(self,key,msg):
        metadata = self.conn.head(self.bucket,key).object.metadata
        email = metadata.get('user','')
        if not email:
            logging.info('no email stored for key %r error %r' % (key, msg))
            return
        if metadata.get('gtfs_crawler','f') == 't':
            email = "jehiah+gtfsarchiver@gmail.com"
            msg += '\n' + str(metadata)
        
        text = """The following error was encountered while processing your GTFS upload.

%s

Please correct the error and re-try this upload.    
<http://www.gtfs-data-exchange.com/upload>    
""" % msg
        EmailUtils.sendEmail(email,'GTFS Upload Error',text)
            

    def run(self):
        while True:
            try:
                for i in self.getItems():
                    try:
                        self.handleItem(i)
                    except StopNow, e:
                        return
                    except DeleteKey, e:
                        self.sendErrorEmail(e.key, e.msg)
                        self.conn.delete(self.bucket, e.key)
                    except:
                        logging.exception('error on handleItem')
                        raise
                        self.reconnect()
            except StopNow, e:
                return
            except:
                logging.exception('error')
                self.reconnect()
            logging.info('sleeping %d' % tornado.options.options.loop_sleep_interval)
            time.sleep(tornado.options.options.loop_sleep_interval)

    def getItems(self):
        for x in self.conn.list_bucket(self.bucket,{'prefix':'queue/'}).entries:
            yield (x.key,self.conn.get(self.bucket,x.key).object)
            logging.info('sleeping %d' % tornado.options.options.upload_sleep_interval)
            time.sleep(tornado.options.options.upload_sleep_interval)

    def gtfs_data_exchange_urlopen(self, req):
        if isinstance(req, (str, unicode)):
            assert req.startswith("http")
            req = urllib2.Request(req)
        assert isinstance(req, urllib2.Request)
        assert isinstance(tornado.options.options.token, (str, unicode))
        req.add_header('X-Crawler-Token', tornado.options.options.token)
        return urllib2.urlopen(req)
        
    def handleItem(self, obj):
        (key, obj) = obj
        logging.debug('handling %r %r' % (key, obj.metadata))
        ## obj has .data and .metadata
        ## .metatdata should be {'user':'me@google.com','comments':'this is a great upload'}
        try:
            z = zipfile.ZipFile(StringIO.StringIO(obj.data))
        except zipfile.BadZipfile, e:
            logging.warning('bad zip archive')
            raise DeleteKey(key, "GTFS .zip Archive is invalid")
        if z.testzip() != None:
            logging.warning('bad zip archive')
            raise DeleteKey(key, "GTFS .zip Archive is invalid")
        agencydata = None
        for n in z.namelist():
            if n.find('_vti_') != -1:
                continue
            if n == 'agency.txt' or n.endswith('/agency.txt'):
                logging.info('reading for %r' % n)
                agencydata = z.read(n)
                logging.info('%r' % agencydata)
                break
        if not agencydata:
            logging.debug('no agency.txt data %r %r %r' % (key, obj.metadata, z.namelist()))
            raise DeleteKey(key, "agency.txt file is missing or invalid in GTFS .zip archive")
            
        ## parse the zip
        ## post the agency text, md5, user, comments, size
        req = urllib2.Request(self.homebase+'crawl/upload')
        req.add_data({'user': obj.metadata.get('user','jehiah+unkownuser@gmail.com'),
                      'comments':obj.metadata.get('comments',''),
                      'sizeoffile':len(obj.data),
                      'md5sum':hashlib.md5(obj.data).hexdigest(),
                      'agencydata':agencydata})
        data = self.gtfs_data_exchange_urlopen(req).read()
        ## if we got 'RENAME:' then rename the file
        if data.startswith('RENAME'):
            newname = data.replace('RENAME:','')
            self.conn.put(self.bucket, newname, None, {'x-amz-copy-source':'/'+self.bucket+'/'+key})
            self.conn.put_acl(self.bucket, newname, '<?xml version="1.0" encoding="UTF-8"?>\n<AccessControlPolicy xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Owner><ID>cf511b009c358c488b479aaf97b797d7d8813e64885c8c331c7371efbb9c7067</ID><DisplayName>jehiah</DisplayName></Owner><AccessControlList><Grant><Grantee xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="CanonicalUser"><ID>cf511b009c358c488b479aaf97b797d7d8813e64885c8c331c7371efbb9c7067</ID><DisplayName>jehiah</DisplayName></Grantee><Permission>FULL_CONTROL</Permission></Grant><Grant><Grantee xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="Group"><URI>http://acs.amazonaws.com/groups/global/AllUsers</URI></Grantee><Permission>READ</Permission></Grant></AccessControlList></AccessControlPolicy>')
            logging.info('renamed %r to %r' % (key, newname))
            self.conn.delete(self.bucket, key)
            # save for future use locally
            if not os.access('/tmp/gtfs/', os.R_OK):
                os.mkdir('/tmp/gtfs')
            outfile = open('/tmp/gtfs/'+newname, 'wb')
            outfile.write(obj.data)
            outfile.close()

            self.sendSuccessEmail(newname,obj.metadata)
            return
        logging.debug('response was %r' % data)
        raise DeleteKey(key, data)
         
if __name__ == "__main__":
    tornado.options.define('environment', default="dev", type=str, help="dev|prod to pick remote endpoints")
    tornado.options.define('token', type=str, help="crawler access token")
    tornado.options.define('skip_uploads', type=bool, default=False, help="skip uploading files")
    tornado.options.define("loop_sleep_interval", type=int, default=240, help="seconds between each program loop")
    tornado.options.define("upload_sleep_interval", type=int, default=60, help="seconds between each file processing (should be >60 seconds for files named with HHMM)")
    
    tornado.options.parse_command_line()
    
    if not tornado.options.options.token:
        sys.stderr.write("you must specify --token\n")
        sys.exit(1)

    BackgroundProcessor().run()
         
         
         
         