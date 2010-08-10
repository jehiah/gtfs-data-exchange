import S3,os,sys
import urllib2
import time
import md5
import zipfile
import StringIO
import MultipartPostHandler
from s3settings import AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY
import EmailUtils
import markdown

# In [2]: conn = S3.AWSAuthConnection('1TRQ62N38DB2SJ7JZT02','l1/NGcNWp207C6nzBaxB5N6uD9/k2LX6kM1OZFKX')
# 
# In [3]: conn.list_bucket('gtfs-devel').entries[0].key
# 
# Out[3]: u'queue/2008-10-28-05:07:03.651274-Y80fbn0m3rqS8guhDfk2.zip'
# 
# In [4]: key = conn.list_bucket('gtfs-devel').entries[0].key
# 
# In [5]: r =conn.put('gtfs-devel','new-key.zip',None,{'x-amz-copy-source':'/gtfs-devel/'+key})


class StopNow:
    pass
    
class DeleteKey:
    def __init__(self,key,msg):
        self.key = key
        self.msg = msg


class BackgroundProcessor:
    def __init__(self):
        if '--remote' in sys.argv:
            self.homebase = 'http://www.gtfs-data-exchange.com/'
            self.bucket = "gtfs"
        else:
            self.homebase = 'http://localhost:8085/'
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
        self.markdown = markdown.Markdown()
        
    def reconnect(self):
        self.conn = S3.AWSAuthConnection(AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY)

    def sendSuccessEmail(self, filename, metadata):
        email = metadata.get('user','')
        comments = self.markdown.convert(metadata.get('comments',''))
        if not email:
            print "error, no email stored", filename, metadata
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
            print "no email stored for key",key,"error",msg
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
                        self.sendErrorEmail(e.key,e.msg)
                        self.conn.delete(self.bucket,e.key)
                    except:
                        raise
                        self.reconnect()
                        print "error on handleItem"
            except StopNow, e:
                return
            except:
                # raise
                self.reconnect()
                print "error occured"
                print sys.exc_info()[0],sys.exc_info()[1]
            print "sleeping"
            time.sleep(120)

    def getItems(self):
        for x in self.conn.list_bucket(self.bucket,{'prefix':'queue/'}).entries:
            yield (x.key,self.conn.get(self.bucket,x.key).object)
            time.sleep(60)
        
    def handleItem(self,obj):
        (key,obj) = obj
        print "handling",key,obj.metadata
        ## obj has .data and .metadata
        ## .metatdata should be {'user':'me@google.com','comments':'this is a great upload'}
        try:
            z = zipfile.ZipFile(StringIO.StringIO(obj.data))
        except zipfile.BadZipfile, e:
            print "bad zip archive",key,obj.metadata
            raise DeleteKey(key,"GTFS .zip Archive is invalid")
        if z.testzip() != None:
            print "bad zip archive",key,obj.metadata
            raise DeleteKey(key,"GTFS .zip Archive is invalid")
        agencydata = None
        for n in z.namelist():
            if n.find('_vti_') != -1:
                continue
            if n == 'agency.txt' or n.endswith('/agency.txt'):
                print "reading for",n
                agencydata = z.read(n)
                print agencydata
                break
        if not agencydata:
            print "no agency.txt data",key,obj.metadata,z.namelist()
            raise DeleteKey(key,"agency.txt file is missing or invalid in GTFS .zip archive")
            
        ## parse the zip
        ## post the agency text, md5, user, comments, size
        req = urllib2.Request(self.homebase+'crawl/upload')
        req.add_data({'user': obj.metadata.get('user','jehiah+unkownuser@gmail.com'),
                      'comments':obj.metadata.get('comments',''),
                      'sizeoffile':len(obj.data),
                      'md5sum':md5.md5(obj.data).hexdigest(),
                      'agencydata':agencydata})
        r= urllib2.urlopen(req).read()
        ## if we got 'RENAME:' then rename the file
        if r.startswith('RENAME'):
            newname = r.replace('RENAME:','')
            self.conn.put(self.bucket,newname,None,{'x-amz-copy-source':'/'+self.bucket+'/'+key})
            self.conn.put_acl(self.bucket,newname,'<?xml version="1.0" encoding="UTF-8"?>\n<AccessControlPolicy xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Owner><ID>cf511b009c358c488b479aaf97b797d7d8813e64885c8c331c7371efbb9c7067</ID><DisplayName>jehiah</DisplayName></Owner><AccessControlList><Grant><Grantee xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="CanonicalUser"><ID>cf511b009c358c488b479aaf97b797d7d8813e64885c8c331c7371efbb9c7067</ID><DisplayName>jehiah</DisplayName></Grantee><Permission>FULL_CONTROL</Permission></Grant><Grant><Grantee xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="Group"><URI>http://acs.amazonaws.com/groups/global/AllUsers</URI></Grantee><Permission>READ</Permission></Grant></AccessControlList></AccessControlPolicy>')
            print "renamed",key,"to",newname, "and made it publicly accessable"
            self.conn.delete(self.bucket,key)
            # save for future use locally
            if not os.access('/tmp/gtfs/',os.R_OK):
                os.mkdir('/tmp/gtfs')
            outfile = open('/tmp/gtfs/'+newname,'wb')
            outfile.write(obj.data)
            outfile.close()

            self.sendSuccessEmail(newname,obj.metadata)
            return
        print "response was ",r
        raise DeleteKey(key,r)
         
if __name__ == "__main__":
    BackgroundProcessor().run()
         
         
         
         