from google.appengine.ext import db
import re
from markdown import Markdown
from google.appengine.api import memcache
import logging
import datetime
import time

def slugify(value):
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)

def rfc3339(d):
    return d.strftime('%Y-%m-%dT%H:%M:%SZ')

class Counter(db.Model):
    count = db.IntegerProperty(default=1)
    name = db.StringProperty(multiline=False,default='')

class Agency(db.Model):
    name = db.StringProperty(multiline=False,default='')
    description = db.StringProperty(multiline=True,default='')
    url = db.StringProperty(multiline=False,default='')
    date_added = db.DateTimeProperty(auto_now_add=True)
    slug = db.StringProperty(multiline=False,default='')
    messagecount = db.IntegerProperty(default=0)
    lastupdate = db.DateTimeProperty(auto_now_add=True)

    license = db.StringProperty(multiline=False,default='')
    feed_baseurl = db.StringProperty(multiline=False,default='')
    license_url = db.StringProperty(multiline=False,default='')

    country_name = db.StringProperty(multiline=False,default='')
    state_name = db.StringProperty(multiline=False,default='')
    area_name = db.StringProperty(multiline=False,default='')

    is_official = db.BooleanProperty(default=False)

    def json(self):
        return  {
            'url':self.url,
            'name':self.name,
            'dataexchange_id':self.slug,
            'dataexchange_url':'http://www.gtfs-data-exchange.com/agency/%s/' % self.slug,
            'country':self.country_name,
            'state':self.state_name,
            'area':self.area_name,
            'feed_baseurl':self.feed_baseurl,
            'license_url':self.license_url,
            'date_added':time.mktime(self.date_added.timetuple()),
            'date_last_updated':time.mktime(self.lastupdate.timetuple()),
            'is_official':self.is_official
        }

    def recent(self):
        return self.lastupdate > (datetime.datetime.now()-datetime.timedelta(days=14))
    
    def isnew(self):
        return self.date_added > (datetime.datetime.now()-datetime.timedelta(days=14))
        
    def rfc3339(self):
        return rfc3339(self.lastupdate)

    def link(self):
        return "/agency/%s/" % self.slug
        
    def location(self):
        d = []
        for x in [self.area_name, self.state_name, self.country_name]:
            if x:
                d.append(x)
        return ', '.join(d)

    def put(self):
        if not self.slug:
            self.slug = slugify(self.name)
            ## if it's in the db already, raise!
            ## TODO: look in cache
            if self.all().filter('slug',self.slug).count() != 0:
                raise "Cant Save, slug already exists"
        db.Model.put(self)
    def display_description(self):
        if not (self.description or '').strip():
            return ''
        m = Markdown()
        return m.convert(self.description)
        
class AgencyAlias(db.Model):
    name = db.StringProperty(multiline=False,default='')
    slug = db.StringProperty(multiline=False,default='')
    date_added = db.DateTimeProperty()
    date_aliased = db.DateTimeProperty(auto_now_add=True)
    real_agency = db.ReferenceProperty(Agency,collection_name='aliases')

class Message(db.Model):
    user = db.UserProperty()
    content = db.TextProperty(default='')
    date = db.DateTimeProperty(auto_now_add=True)
    hasFile = db.BooleanProperty(default=False)
    filename = db.StringProperty(multiline=False)
    md5sum = db.StringProperty(multiline=False)
    size = db.IntegerProperty()
    validation_results = db.TextProperty(default='')
    validated = db.BooleanProperty(default=False)
    validated_on = db.DateTimeProperty()

    def agencies(self):
        a = getattr(self,'_agencies',None)
        #logging.debug('getattr' + str(a))
        if a:
            return a
        k = 'message.agencies.%s' % self.key()
        a = memcache.get(k)
        if a:
            self._agencies = a
            return a
        a = []
        try:
            for x in MessageAgency.all().filter('message =',self).order('agency').fetch(50):
                a.append((x.agency.name,x.agency))
        except:
            pass
        a.sort()
        a = [x[1] for x in a]
        self._agencies = a
        memcache.set(k,a,60*60*24*7) # cached for a short period of time because this could change with AgencyAliases
        return a
            
    def rfc3339(self):
        return rfc3339(self.date)

    def filelink(self,production=None):
        if not self.hasFile:
            return ''
        if production == True:
            return 'http://gtfs.s3.amazonaws.com/' + self.filename
        elif production == False:
            return 'http://gtfs-devel.s3.amazonaws.com/' + self.filename
        else:
            return "/gtfs/"+ (self.filename or '')
    
    def json(self):
        agencies = [x.slug for x in self.agencies()]
        return dict(
            filename=self.filename,
            agencies=agencies,
            uploaded_by_user=str(self.user),
            md5sum=self.md5sum,
            size=self.size,
            date_added=time.mktime(self.date.timetuple()),
            description=self.content,
            file_url=self.filelink(production=True) #TODO: make this value dynamic
        )

# class ValidationResult(db.Model):
#     message = db.ReferenceProperty(Message)
#     validation_results = db.TextProperty(default='')
#     validated_on = db.DateTimeProperty()
# 
# class TableInspection(db.Model):
#     message = db.ReferenceProperty(Message)
#     filename = db.StringProperty(multiline=False)
#     columns = db.StringProperty(multiline=False)
#     content = db.TextProperty(default='')

class MessageAgency(db.Model):
    agency = db.ReferenceProperty(Agency,collection_name='messages_set')
    message = db.ReferenceProperty(Message,collection_name='agencies_set')
    date = db.DateTimeProperty(auto_now_add=True)
    hasFile = db.BooleanProperty(default=False)

## Crawler Stuff

class CrawlBaseUrl(db.Model):
    url = db.LinkProperty()
    lastcrawled = db.DateTimeProperty(auto_now_add=True)
    recurse = db.IntegerProperty(default=1)
    download_as = db.StringProperty(multiline=False,default='gtfs-archiver')
    show_url = db.BooleanProperty(default=True)
    post_text = db.StringProperty(multiline=False,default='')
    # agency = db.ReferenceProperty(agency)
    def asMapping(self):
        return {'url' : self.url,
                'recurse' : self.recurse,
                'download_as' : self.download_as,
                'show_url' : self.show_url,
                'post_text' : self.post_text}
        #       'agency_slug' : self.agency and self.agency.slug or None
    
class CrawlUrl(db.Model):
    url = db.LinkProperty()
    lastseen = db.DateTimeProperty(auto_now_add=True)
    headers = db.TextProperty()

class CrawlSkipUrl(db.Model):
    url = db.LinkProperty()
    lastseen = db.DateTimeProperty(auto_now_add=True)
    added_on = db.DateTimeProperty(auto_now_add=True)

class SkipMd5(db.Model):
    md5sum = db.StringProperty(multiline=False)
    reason = db.TextProperty()
    
    # def markdownLink(self):
    #     if self.contentType.startswith("image"):
    #         return "![%s](/file/%s)" % (str(self.name),str(self.name))
    #     return "[%s](/file/%s)" % (str(self.name),str(self.name))
