#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from functools import wraps
import wsgiref.handlers
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.api import mail

import webapp as webapp2
import model
import random,string,datetime,logging,os
import utils
import csv
import codecs
import types
import cStringIO
from django.utils import simplejson as json


from django.core.paginator import ObjectPaginator

random.seed()

def login_required(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return
        else:
            return method(self, *args, **kwargs)
    return wrapper


def admin_required(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return
        elif not users.is_current_user_admin():
            return self.error(403)
        else:
            return method(self, *args, **kwargs)
    return wrapper

def crawler_required(method):
    @wraps(method)
    def wrapper(self,*args,**kwargs):
        auth = self.request.headers.get('Authorization',None)
        logging.info('auth = ' + str(auth))
        if auth != 'Basic Y3Jhd2xlcjpjcmF3bGVy': ## crawler,crawler
            self.response.headers['WWW-Authenticate'] = 'Basic realm="RESTRICTED ACCESS"'
            return self.error(401)
        return method(self,*args,**kwargs)
    return wrapper

class BaseController(webapp2.RequestHandler):
    def __init__(self):
        self.template = 'index.html'
        current_userisadmin = False
        if users.get_current_user() and users.is_current_user_admin():
            current_userisadmin = True
        self.template_vals = { 'current_userisadmin':current_userisadmin}

    # def __before__(self,*args):
    #     pass
    # 
    # def __after__(self,*args):
    #     pass
    def head(self):
        self.response.headers['Allow'] = 'GET'
        return self.error(405)

    def errorb(self, errorcode, message='an error occured'):
        if errorcode == 404:
            message = 'Sorry, we were not able to find the requested page.  We have logged this error and will look into it.'
        elif errorcode == 403:
            message = 'Sorry, that page is reserved for administrators.  '
        elif errorcode == 500:
            message = "Sorry, the server encountered an error.  We have logged this error and will look into it."
        return self.render('views/error.html',{'message':message})

    def render(self, template_file, template_vals={}):
        """
        Helper method to render the appropriate template
        """
        if users.get_current_user():
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
        self.production = self.request.url.find('www.gtfs-data-exchange.com')!= -1
        template_vals.update({'url':url,
                             'url_linktext':url_linktext,
                             'user':users.get_current_user(),
                             'production':self.production})
        template_vals.update(self.template_vals)
        path = os.path.join(os.path.dirname(__file__), template_file)
        self.response.out.write(template.render(path, template_vals))


class BasePublicPage(BaseController):
    """
    Do all the common public page prep such as nav pages etc
    """
    def __before__(self,*args):
        self.production = self.request.url.find('www.gtfs-data-exchange.com')!= -1
        self.template_vals.update({'baseurl':self.request.url[:self.request.url.find('/',7)]})

class StaticPage(BasePublicPage):
    def get(self):
        self.render('views/'+ self.request.uri.split('/')[-1] + '.html')

class SubmitFeedPage(StaticPage):
    # get will work automagically
    def post(self):
        ## send an email; render "thank you"
        
        feed_location = self.request.POST.get('feed_location')
        if not feed_location:
            return self.render('views/generic.html',{'error':'Feed Location is required'})
            
        agency_name = self.request.POST.get('agency_name')
        agency_location = self.request.POST.get('agency_location')
        contact_info = self.request.POST.get('contact_info')
        if users.get_current_user():
            user = users.get_current_user().email()
        else:
            user = ''
        
        mail.send_mail(sender="Jehiah Czebotar <jehiah@gmail.com>",
                      to="Jehiah Czebotar <jehiah@gmail.com>",
                      subject="New GTFS Feed - %s" % (agency_name or feed_location),
                      body="""
Feed URL: %(feed_location)s
Agency Name: %(agency_name)s
Agency Location: %(agency_location)s
Point of Contact: %(contact_info)s
Logged In User: %(user)s
        """ % {
        'agency_name' : agency_name,
        'agency_location' : agency_location,
        'contact_info' : contact_info,
        'feed_location' : feed_location,
        'user' : user
        })
        
        self.render('views/generic.html',{'message':'Thank You For Your Submission'})

class BaseAPIPage(webapp2.RequestHandler):
    def head(self):
        self.response.headers['Allow'] = 'GET'
        return self.error(405)

    def get(self):
        self.api_error(500,"UNKNOWN_ERROR")

    def post(self):
        self.api_error(405,"POST_NOT_SUPPORTED")

    def api_error(self, status_code, status_txt):
        self.api_response(None, status_code, status_txt)
    
    def api_response(self, data, status_code=200, status_txt="OK"):
        logging.info('returning %s' % data)
        out_data = {
            'status_code':status_code,
            'status_txt':status_txt,
            'data':data
        }
        callback = self.request.GET.get('callback',None)
        if callback:
            self.response.headers['Content-type'] = 'application/jsonp'
            self.response.out.write(callback+'(')
            self.response.out.write(json.dumps(out_data))
            self.response.out.write(')')
        else:
            self.response.headers['Content-type'] = 'application/javascript'
            self.response.out.write(json.dumps(out_data))

class RedirectAgencyList(BasePublicPage):
    def get(self):
        self.redirect('/agencies')

class APIAgencyPage(BaseAPIPage):
    def get(self, slug):
        s = utils.lookupAgencyAlias(slug)
        logging.warning('new slug %s '% s)
        if s:
            slug = s
        agency = utils.getAgency(slug)
        logging.warning('agency %s' % agency )
        if not agency:
            return self.api_error(404, 'AGENCY_NOT_FOUND')
        messages =model.MessageAgency.all().filter('agency',agency).order('-date').fetch(1000)
        messages = [message.message.json() for message in messages if message.hasFile]
        self.api_response(dict(
            agency=agency.json(),
            datafiles=messages
        ))


class APIAgencies(BaseAPIPage):
    def get(self):
        agencies = utils.getAllAgencies()
        response = [agency.json() for agency in agencies]
        if self.request.GET.get('format',None)== "csv":
            csvwriter = UnicodeWriter(self.response.out)
            headers = response[0].keys()
            csvwriter.writerow(headers)
            for row in response:
                csvwriter.writerow(row.values())
            return
        
        self.api_response(response)
        

class UnicodeWriter:
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        d = []
        for x in row:
            if type(x) in types.StringTypes:
                d.append(x.encode('utf-8'))
            else:
                d.append(str(x))
        self.writer.writerow(d)
        # self.writer.writerow([s.encode("utf-8") for s in row])
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)
            
class Agencies(BasePublicPage):
    def get(self):
        agencies = utils.getAllAgencies()
            
        grouped = {}
        for agency in agencies:
            letter = agency.name[0].upper()
            if letter not in grouped:
                grouped[letter] = []
            grouped[letter].append(agency)
            
        grouped = grouped.items()
        grouped.sort() 
        agency_count = utils.getAgencyCount()
        
        self.render('views/agencies.html', {'agencies':agencies, 'grouped_agencies':grouped, 'agency_count':agency_count})

class AgenciesByLocation(BasePublicPage):
    def get(self):
        agencies = utils.getAllAgencies()
        data = [[agency.country_name, agency.state_name, agency.name, agency] for agency in agencies]
        data.sort()
        agencies = [x[-1] for x in data]
        agency_count = utils.getAgencyCount()

        self.render('views/agencies_bylocation.html', {'agencies':agencies, 'agency_count':agency_count})

class AgenciesByLastUpdate(BasePublicPage):
    def get(self):
        agencies = utils.getAllAgencies()
        data = [[agency.lastupdate, agency] for agency in agencies]
        data.sort(reverse=True)
        agencies = [x[-1] for x in data]
        agency_count = utils.getAgencyCount()

        self.render('views/agencies_bylastupdate.html', {'agencies':agencies, 'agency_count':agency_count})

class AgenciesAsTable(Agencies):
    def get(self):
        agencies = utils.getAllAgencies()
        agency_count = utils.getAgencyCount()

        self.render('views/agencies_astable.html', {'agencies':agencies, 'agency_count':agency_count})

class MainPage(BasePublicPage):
    def get(self):
        recentAgencies = utils.getRecentAgencies()
        recentMessages = utils.getRecentMessages()
        self.render('views/index.html', {'recentMessages':recentMessages, 
                                        'recentAgencies':recentAgencies})

class CommentPage(BasePublicPage):
    def get(self,key=None):
        if not key:
            return self.error(404)
        if not key.isdigit():
            try:
                obj = db.get(db.Key(key))
                return self.redirect('/meta/%d' % obj.key().id())
            except:
                logging.exception('key not found %s' % key)
                return self.error(404)
            
        try:
            obj = model.Message.get_by_id(int(key))
            # obj = db.get(db.Key(key))
        except:
            logging.exception('key not found %s' % key)
            return self.error(404)
        if not obj:
            return self.error(404)
        self.render('views/comment.html',{'msg':obj})

class CommentAdminPage(BasePublicPage):
    @admin_required
    def get(self,key=None):
        if not key:
            return self.error(404)
        try:
            obj = db.get(db.Key(key))
        except:
            return self.error(404)
        if not obj:
            return self.error(404)
        self.render('views/commentAdmin.html',{'msg':obj})
    @admin_required
    def post(self,key=None):
        try:
            obj = db.get(db.Key(key))
        except:
            return self.error(404)
        obj.content = self.request.POST.get('comments',obj.content)
        obj.put()
        self.redirect('/meta/%d' % obj.key().id())


class QueuePage(BasePublicPage):
    #@login_required
    def get(self):
        if not self.request.GET.get('key','') or not self.request.GET.get('bucket','').startswith('gtfs'):
            return self.redirect('/upload')
        self.render('views/queue.html')


class FeedPage(BasePublicPage):
    def get(self, userOrAgency=None, id=None):
        context = {'userOrAgency':userOrAgency,'u':id,'id':id}
        self.response.headers['Content-Type'] = 'application/atom+xml'
        if not userOrAgency:
            context['messages'] = model.Message.all().filter('date >',datetime.datetime.now()-datetime.timedelta(30)).order('-date').fetch(25)
            self.render('views/atom.xml',context)
        elif userOrAgency == 'user':
            import urllib
            user = urllib.unquote(id)
            if '@' in user:
                u = users.User(user)
            else:
                u = users.User(user+'@gmail.com')
            context['messages'] = model.Message.all().filter('date >',datetime.datetime.now()-datetime.timedelta(30)).filter('user =', u).order('-date').fetch(25)
            self.render('views/agency_atom.xml',context)
        elif userOrAgency == 'agency':
            s = utils.lookupAgencyAlias(id)
            if s:
                return self.redirect('/%s/%s/feed' % (userOrAgency,s))
            
            agency = model.Agency.all().filter('slug =',id).get()
            context['agency'] = agency
            context['messages'] = [x.message for x in model.MessageAgency.all().filter('agency =',agency).filter('date >',datetime.datetime.now()-datetime.timedelta(30)).order('-date').fetch(25)]
            self.render('views/agency_atom.xml',context)

class UserPage(BasePublicPage):
    def get(self,user):
        import urllib
        user = urllib.unquote(user)
        if '@' in user:
            u = users.User(user)
        else:
            u = users.User(user+'@gmail.com')
        messages= model.Message.all().filter('user =',u).order('-date').fetch(1000)

        if not messages and not users.get_current_user():
            return self.error(404)
        if not messages and users.get_current_user().email() != u.email():
            return self.error(404)

        paginator = ObjectPaginator(messages, 15,1)
        try:
            page = int(self.request.GET.get('page', '1'))
        except ValueError:
            page = 1
            
        try:
            records = paginator.get_page(page-1)
        except:
            records = paginator.get_page(0)
            page = 1  
        self.render('views/user.html',{'u':u,'messages':records,'paginator':paginator,
        "next" : paginator.has_next_page(page-1),'previous':paginator.has_previous_page(page-1),'previous_page_number':page-1,'next_page_number':page+1,"page" : page})

class LatestAgencyFile(BasePublicPage):
    def get(self,slug):
        s = utils.lookupAgencyAlias(slug)
        if s:
            return self.redirect('/agency/%s/' % (s))
        agency = utils.getAgency(slug)
        if not agency:
            return self.error(404)
        message =model.MessageAgency.all().filter('agency',agency).order('-date').fetch(1)
        if message:
            return self.redirect(message[0].message.filelink())
        return self.error(404)
        
        
    
class AgencyPage(BasePublicPage):
    def get(self,slug):
        s = utils.lookupAgencyAlias(slug)
        if s:
            return self.redirect('/agency/%s/' % (s))

        agency = utils.getAgency(slug)
        if not agency:
            return self.error(404)
        messages =model.MessageAgency.all().filter('agency',agency).order('-date').fetch(1000)
        self.render('views/agency.html',{'agency':agency,'messages':messages})

    @login_required
    def post(self,slug):
        key = 'Agency.slug.%s' % slug
        agency = memcache.get(key)
        if not agency:
            agency = model.Agency.all().filter('slug =',slug).get()
            if not agency:
                return self.error(404)
            memcache.set(key,agency)
        if not self.request.POST.get('comments',''):
            self.redirect(agency.link())
        m = model.Message(user=users.get_current_user(),content=self.request.POST.get('comments',''))
        m.put()
        ma = model.MessageAgency()
        ma.message = m
        ma.hasFile = False
        ma.agency = agency
        ma.put()
        memcache.delete('Message.recent')
        self.redirect(agency.link())
        
class AgencyEditPage(BasePublicPage):
    @admin_required
    def get(self,slug):
        s = utils.lookupAgencyAlias(slug)
        if s:
            return self.redirect('/agency/%s/edit' % (s))

        key = 'Agency.slug.%s' % slug
        agency = memcache.get(key)
        if not agency:
            agency = model.Agency.all().filter('slug =',slug).get()
            if not agency:
                return self.error(404)
            memcache.set(key,agency)

        self.render('views/AgencyEdit.html',{'agency':agency})

    @login_required
    def post(self,slug):
        key = 'Agency.slug.%s' % slug
        agency = memcache.get(key)
        if not agency:
            agency = model.Agency.all().filter('slug =',slug).get()
            if not agency:
                return self.error(404)
        
        # agency.name = self.request.POST.get('name',agency.name)
        # agency.slug = self.request.POST.get('slug',agency.slug)
        agency.description = self.request.POST.get('description',agency.description)
        agency.url = self.request.POST.get('url',agency.url)
        
        agency.country_name = self.request.POST.get('country',agency.country_name).strip()
        agency.state_name = self.request.POST.get('state',agency.state_name).strip()
        agency.area_name = self.request.POST.get('area',agency.area_name).strip()
        agency.feed_baseurl = self.request.POST.get('feed',agency.feed_baseurl).strip()
        agency.license_url = self.request.POST.get('license',agency.license_url).strip()
        agency.is_official = self.request.POST.get('official','0') == '1'
        
        # agency.lastupdate = datetime.datetime.now() # this is for the last message 'update'
        agency.put()
        memcache.delete(key)
        #memcache.delete('Agency.recent')
        memcache.delete('Agency.all')
        memcache.set('Agency.slug.%s' % agency.slug,agency)
        
        self.render('views/generic.html',{'message':'Agency %s updated' % agency.name})

class UploadError(Exception):
    def __init__(self,msg):
        logging.warning('upload error ' + str(msg))
        self.msg = msg
    def __str__(self):
        return str(self.msg)


def uploadfile(username,agencydata,comments,md5sum,sizeoffile):
    ## todo: cache
    if model.Message.all().filter('md5sum =',md5sum).count() >0:
        raise UploadError('This file has previously been uploaded')
    ## todo: cache
    if model.SkipMd5.all().filter('md5sum =',md5sum).count() >0:
        raise UploadError('This file has previously been uploaded')

    raw_agencies = utils.readfile(agencydata)
    if not raw_agencies:
        raise UploadError("zip file did not contain any valid agencies in agency.txt.")

    ## save our msg
    m = model.Message(user=username,content=comments)
    m.hasFile = True
    memcache.delete('Message.recent')
    # m.filename = filename
    m.md5sum = md5sum
    m.size = sizeoffile
    m.put()
    
    d = datetime.datetime.now()
    datestr = d.strftime('%Y%m%d_%H%M')
    for ag in raw_agencies:
        ## get from the db
        ## lookup by url first
        
        a = None
        if ag.get('agency_url','').strip():
            ## try to get via url first as it's more unique
            a = model.Agency.all().filter('url =',ag['agency_url'].strip()).get()
        if not a:
            slug = model.slugify(ag['agency_name'].strip())
            s = utils.lookupAgencyAlias(slug)
            if s:
                slug = s
            a = memcache.get('Agency.slug.%s' % slug)
            if not a:
                a = model.Agency.all().filter('slug =',slug).get()
        if a:
            a.messagecount +=1
            a.lastupdate = datetime.datetime.now()
            a.put()
            memcache.set('Agency.slug.%s' % a.slug,a)
        if not a:
            a = model.Agency()
            a.name = ag['agency_name'].strip()
            a.url = ag.get('agency_url','')
            a.messagecount = 1
            a.put()
            memcache.delete('Agency.recent')
            utils.incrAgencyCount()
            
        if len(raw_agencies) == 1:
            m.filename = '%s_%s.zip' % (a.slug,datestr)
            m.put()

        ma= model.MessageAgency()
        ma.agency = a
        ma.message = m
        ma.hasFile=True
        ma.put()
        memcache.delete('Agency.all') # because it has the cached last-update

    if not m.filename:
        m.filename = '%s_%s.zip' % (username.nickname(),datestr)
        m.put()

    recentFiles = model.Message.all().filter('hasFile =',True).filter('date >=',datetime.datetime(d.year,d.month,d.day,d.hour,d.minute)).count()
    if recentFiles > 1: # note we already saved *this* filename
        m.filename= m.filename.replace('.zip','_%d.zip' % recentFiles)
        m.put()

    ## send email to user ?

    return m.filename

class UploadFile(BasePublicPage):
    @login_required
    def get(self):
        if self.production:
            policy="CnsiZXhwaXJhdGlvbiI6ICIyMDExLTAxLTAxVDAwOjACnsiZXhwaXJhdGlvbiI6ICIyMDEyLTAxLTAxVDAwOjAwOjAwWiIsCiAgImNvbmRpdGlvbnMiOiBbIAogICAgeyJidWNrZXQiOiAiZ3RmcyJ9LCAKICAgIFsic3RhcnRzLXdpdGgiLCAiJGtleSIsICJxdWV1ZS8iXSwKICAgIHsiYWNsIjogInByaXZhdGUifSwKICAgIHsic3VjY2Vzc19hY3Rpb25fcmVkaXJlY3QiOiAiaHR0cDovL3d3dy5ndGZzLWRhdGEtZXhjaGFuZ2UuY29tL3F1ZXVlIn0sCiAgICBbInN0YXJ0cy13aXRoIiwgIiRDb250ZW50LVR5cGUiLCAiIl0sCiAgICBbImNvbnRlbnQtbGVuZ3RoLXJhbmdlIiwgMCwgMzE0NTcyODBdLAogICAgWyJzdGFydHMtd2l0aCIsIiR4LWFtei1tZXRhLXVzZXIiLCIiXSwKICAgIFsic3RhcnRzLXdpdGgiLCIkeC1hbXotbWV0YS1jb21tZW50cyIsIiJdCiAgICBdCn0K"
            signature = "PBl6mIjwbAiWK5ddFHNR6vbf53w="
        else:
            policy = "CnsiZXhwaXJhdGlvbiI6ICIyMDExLTAxLTAxVDAwOjAwOjAwWiIsCiAgImNvbmRpdGlvbnMiOiBbIAogICAgeyJidWNrZXQiOiAiZ3Rmcy1kZXZlbCJ9LCAKICAgIFsic3RhcnRzLXdpdGgiLCAiJGtleSIsICJxdWV1ZS8iXSwKICAgIHsiYWNsIjogInByaXZhdGUifSwKICAgIHsic3VjY2Vzc19hY3Rpb25fcmVkaXJlY3QiOiAiaHR0cDovL2xvY2FsaG9zdDo4MDgxL3F1ZXVlIn0sCiAgICBbInN0YXJ0cy13aXRoIiwgIiRDb250ZW50LVR5cGUiLCAiIl0sCiAgICBbImNvbnRlbnQtbGVuZ3RoLXJhbmdlIiwgMCwgMzE0NTcyODBdLAogICAgWyJzdGFydHMtd2l0aCIsIiR4LWFtei1tZXRhLXVzZXIiLCIiXSwKICAgIFsic3RhcnRzLXdpdGgiLCIkeC1hbXotbWV0YS1jb21tZW50cyIsIiJdCiAgICBdCn0K"
            signature="C2wGDUj7kyN1bJ+jhLc662iZsXc="
        randstring = ''.join([random.choice(string.letters+string.digits) for x in range(20)])
        nextkey = str(datetime.datetime.now())+'-'+randstring+'.zip'
        self.render('views/upload.html',{'policy':policy,'signature':signature,'nextkey':nextkey.replace(' ','-')})

    @login_required
    def post(self):
        if 'upload_file' not in self.request.POST:
            self.error(400)
            self.response.out.write("file not specified!")
            return
        if (self.request.POST.get('upload_file', None) is None or 
           not self.request.POST.get('upload_file', None).filename):
            self.error(400)
            self.response.out.write("file not specified!")
            return

        name = self.request.POST.get('upload_file').filename
        logging.info('upload file name ' + str(name))

        filedata = self.request.POST.get('upload_file').file.read()
        contentType = self.request.POST.get('upload_file').type ## check that it's zip!

        try:
            redirect_url = uploadfile(username=users.get_current_user(),filename=name,filedata=filedata,contentType=contentType,comments=self.request.POST.get('comments',''))
        except UploadError, e:
            self.error(400)
            return self.response.out.write(e.msg)
        
        self.redirect(redirect_url)
        
class ZipFilePage(BasePublicPage):
    def __before__(self,*args):
        pass

    def get(self,name):
        key = 'DataFile.name.%s' % name
        f = memcache.get(key)
        if not f:
            f = model.Message.all().filter('filename =',name).get()
            memcache.set(key,f)
        production = self.request.url.find('www.gtfs-data-exchange.com')!= -1

        if f:
            return self.redirect(f.filelink(production=production))
        else:
            return self.error(404)

class ManageAliases(BasePublicPage):
    @admin_required
    def __before__(self,*args):
        pass
        
    def get(self):
        ## Get agencies ??
        agencies = memcache.get('Agency.all')
        if not agencies:
            agencies = model.Agency.all().order('name').fetch(200)
            memcache.set('Agency.all',agencies)
        
        self.render('views/ManageAliases.html',{'agencies':agencies})

    def post(self):
        f = self.request.POST.get('from_agency','')
        t = self.request.POST.get('to_agency','')
        if not t or f == t:
            return self.render('views/ManageAliases.html',{'error':'Select an agency to merge from, and one to merge to'})
        
        if not f and  (not self.request.POST.get('to_name','') or not self.request.POST.get('to_slug','')):
            return self.render('views/ManageAliases.html',{'error':'new name and slug must be selected when only selecting the "to" agency'})
        
        if f:
            f = db.get(db.Key(f))
        t = db.get(db.Key(t))

        if not t or f == t:
            return self.render('views/ManageAliases.html',{'error':'Select an agency to merge from, and one to merge to'})
        
        ## go through the messages
        if f:
            for m in model.MessageAgency.all().filter('agency =',f).fetch(500):
                m.agency=t
                m.put()
        else:
            ## we are merging from an old name/alias
            f = db.get(db.Key(self.request.POST.get('to_agency',''))) ## re-fetch the new one as the old one
            t.name = self.request.POST.get('to_name','')
            t.slug = self.request.POST.get('to_slug','')
            t.put()
        
        aa = model.AgencyAlias()
        aa.name = f.name
        aa.date_added = f.date_added
        aa.slug = f.slug
        aa.real_agency=t
        aa.put()
        
        if f.key() != t.key(): ## make sure they were diferent items
            f.delete()
            utils.decrAgencyCount()
        memcache.delete('Message.recent')
        memcache.delete('Agency.all')
        memcache.delete('Agency.slug.%s' % aa.slug)
        memcache.delete('AgencyAlias.slug.%s' % aa.slug)
        
        self.render('views/generic.html',{'message':'Agency Meregd Successfully'})

class CrawlNextUrl(BaseController):
    @crawler_required
    def get(self):
        if self.request.GET.get('timeframe',''):
            d = datetime.datetime.now() - datetime.timedelta(minutes=30)
        else:
            d = datetime.datetime.now() - datetime.timedelta(hours=12)
        #d = datetime.datetime.now() + datetime.timedelta(hours=1)
        u = model.CrawlBaseUrl.all().filter('lastcrawled <',d).order('-lastcrawled').get()
        if not u:
            return self.response.out.write('NONE')
        logging.debug(str('returning ' + str(u.url) + ' to be cralwed'))
        u.lastcrawled = datetime.datetime.now()
        u.put()
        self.response.out.write(str(u.asMapping()))


        
class CrawlerMain(BaseController):
    @admin_required
    def get(self):
        crawlurls = model.CrawlBaseUrl.all().order('lastcrawled').fetch(1000)
        self.render('views/CrawlerMain.html',{'crawlurls':crawlurls})

    def post(self):
        if self.request.POST.get('orig_url'):
            c = model.CrawlBaseUrl().all().filter('url =',self.request.POST.get('orig_url')).get()
        else:
            c = model.CrawlBaseUrl()
            c.lastcrawled = datetime.datetime.now()-datetime.timedelta(days=365)
        c.url = self.request.POST.get('url')
        c.recurse = int(self.request.POST.get('recurse'))
        c.download_as = self.request.POST.get('download_as','gtfs-archiver')
        c.show_url = self.request.POST.get('show_url',True) == 'True'
        c.post_text = self.request.POST.get('post_text','')
        c.put()
        self.redirect('/crawl')

class CrawlHeaders(BaseController):
    @crawler_required
    def get(self):
        url = self.request.GET.get('url','')
        c = model.CrawlUrl.all().filter('url =',url).order('-lastseen').get()
        if not c:
            return self.response.out.write('NONE')
        self.response.out.write(c.headers)

    @crawler_required
    def post(self):
        url = self.request.POST.get('url','')
        c = model.CrawlUrl()
        c.url = url
        c.headers = self.request.POST['headers']
        c.save()
        self.response.out.write('OK')

class CrawlShouldSkip(BaseController):
    @crawler_required
    def get(self):
        url = self.request.GET.get('url','')
        c= model.CrawlSkipUrl.all().filter('url =',url).get()
        if c:
            c.lastseen = datetime.datetime.now()
            c.put()
            return self.response.out.write('YES')
        self.response.out.write('NO')
        
class CrawlUndoLastRun(BaseController):
    @crawler_required
    def post(self):
        t = datetime.datetime.now()-datetime.timedelta(hours=12)
        a=0
        b=0
        for c in model.CrawlBaseUrl.all().filter('lastcrawled >=',t).fetch(500):
            a+=1
            c.lastcrawled -= datetime.timedelta(hours=24)
            c.put()
        
        ## now get delete the headers that were saved
        for u in model.CrawlUrl.all().filter('lastseen >=',t).fetch(1000):
            b +=1
            u.delete()
        
        self.response.out.write('%d %d' % (a,b))

class CrawlUpload(BaseController):
    @crawler_required
    def get(self):
        md5sum = self.request.GET.get('md5sum','')
        if md5sum and model.Message.all().filter('md5sum =',md5sum).count() >0:
            self.response.out.write('FOUND')
        elif md5sum and model.SkipMd5.all().filter('md5sum =',md5sum).count() >0:
            self.response.out.write('FOUND-skipped')
        else:
            self.response.out.write('NOT_FOUND')

    ## don't require crawler here so we don't have to double post
    def post(self):
        ## file is in upload_file
        agencydata = self.request.POST.get('agencydata')
        comments = self.request.POST.get('comments')
        username = users.User(self.request.POST.get('user'))
        md5sum = self.request.POST.get('md5sum')
        sizeoffile = int(self.request.POST.get('sizeoffile'))
        try:
            filename = uploadfile(username=username,agencydata=agencydata,comments=comments,md5sum=md5sum,sizeoffile=sizeoffile)
        except UploadError, e:
            return self.response.out.write('ERROR : ' + str(e.msg))
        return self.response.out.write('RENAME:'+filename)

class ValidationResults(BaseController):
    # @crawler_required
    def get(self):
        ## get's oldest first
        m = model.Message.all().filter('validated =',False).filter('hasFile =',True).order('date').get()
        if m:
            self.response.out.write('FILE:'+m.filename)
        else:
            self.response.out.write('OK')

    def post(self):
        filename = self.request.POST.get('filename')
        md5sum = self.request.POST.get('md5sum')
        results = self.request.POST.get('results')
        f = model.Message.all().filter('md5sum =',md5sum).filter('filename =',filename).get()
        if not f:
            self.response.out.write('NOT_FOUND')
        else:
            f.validation_results = results
            f.validated = True
            f.validated_on = datetime.datetime.now()
            f.put()
            self.response.out.write('UPDATED')

def real_main():
    application = webapp2.WSGIApplication2(
                  [
                  #('/sitemap.xml',Sitemap),
                   ('/', MainPage),
                   ('/how-to-provide-open-data', StaticPage),
                   ('/submit-feed', SubmitFeedPage),
                   ('/upload', UploadFile),
                   ('/queue', QueuePage),
                   ('/feed',FeedPage),
                   ('/meta/(?P<key>.*?)/edit/?',CommentAdminPage),
                   ('/meta/(?P<key>.*?)/?',CommentPage),
                   ('/(?P<userOrAgency>user)/(?P<id>.*?)/feed/?',FeedPage),
                   ('/user/(?P<user>.*?)/?',UserPage),
                   ('/(?P<userOrAgency>agency)/(?P<id>.*?)/feed/?',FeedPage),
                   ('/agency/',RedirectAgencyList),
                   ('/agencies/bylocation',AgenciesByLocation),
                   ('/agencies/bylastupdate',AgenciesByLastUpdate),
                   ('/agencies/astable',AgenciesAsTable),
                   ('/agencies',Agencies),
                   ('/agency/(?P<slug>.*?).json$',APIAgencyPage),
                   ('/agency/(?P<slug>.*?)/latest.zip',LatestAgencyFile),
                   ('/agency/(?P<slug>.*?)/edit',AgencyEditPage),
                   ('/agency/(?P<slug>.*?)/?',AgencyPage),
                   ('/gtfs/(?P<name>.*\.zip)',ZipFilePage),
                   ('/manage/',ManageAliases),
                   ('/crawl/nexturl',CrawlNextUrl),
                   ('/crawl/?',CrawlerMain),
                   ('/crawl/headers',CrawlHeaders),
                   ('/crawl/shouldSkip',CrawlShouldSkip),
                   ('/crawl/upload',CrawlUpload),
                   ('/crawl/undoLastRun',CrawlUndoLastRun),
                   ('/ValidationResults',ValidationResults),
                   ('/api/agencies',APIAgencies),
                   ],debug=True)
    wsgiref.handlers.CGIHandler().run(application)

def profile_main():
    # This is the main function for profiling 
    # We've renamed our original main() above to real_main()
    import cProfile, pstats
    prof = cProfile.Profile()
    prof = prof.runctx("real_main()", globals(), locals())
    print "<pre>"
    stats = pstats.Stats(prof)
    stats.sort_stats("time")  # Or cumulative
    stats.print_stats(120)  # 80 = how many to print
    # The rest is optional.
    # stats.print_callees()
    # stats.print_callers()
    print "</pre>"

#main = profile_main
main = real_main
template.register_template_library('common.templatefilters')

if __name__ == '__main__':
    # logging.getLogger().setLevel(logging.info)
    main()


