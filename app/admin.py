from google.appengine.ext import db
from google.appengine.api import memcache

import model
import app.basic
import utils
import datetime

class AdminIndex(app.basic.BaseController):
    @app.basic.admin_required
    def get(self):
        self.render('templates/admin_index.html')

class AdminAliases(app.basic.BasePublicPage):
    @app.basic.admin_required
    def __before__(self, *args):
        pass
    
    def get(self):
        agencies = utils.get_all_agencies()
        aliases = utils.get_all_aliases()
        self.render('templates/admin_aliases.html', {'agencies':agencies, 'aliases':aliases})
    
    def post(self):
        f = self.request.POST.get('from_agency', '')
        t = self.request.POST.get('to_agency', '')
        if not t or f == t:
            return self.render('templates/admin_aliases.html', {'error':'Select an agency to merge from, and one to merge to'})
        
        if not f and  (not self.request.POST.get('to_name', '') or not self.request.POST.get('to_slug', '')):
            return self.render('templates/admin_aliases.html', {'error':'new name and slug must be selected when only selecting the "to" agency'})
        
        if f:
            f = db.get(db.Key(f))
        t = db.get(db.Key(t))
        
        if not t or f == t:
            return self.render('templates/admin_aliases.html', {'error':'Select an agency to merge from, and one to merge to'})
        
        ## go through the messages
        if f:
            for m in model.MessageAgency.all().filter('agency =', f).fetch(500):
                m.agency=t
                m.put()
        else:
            ## we are merging from an old name/alias
            f = db.get(db.Key(self.request.POST.get('to_agency', ''))) ## re-fetch the new one as the old one
            t.name = self.request.POST.get('to_name', '')
            t.slug = self.request.POST.get('to_slug', '')
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
        
        self.render('templates/generic.html', {'message':'Agency Merged Successfully'})


class AgencyEditPage(app.basic.BasePublicPage):
    @app.basic.admin_required
    def get(self, slug):
        # TODO: should we even do this on an admin page? admin links should always be golden
        s = utils.lookup_agency_alias(slug)
        if s:
            return self.redirect('/a/edit/%s' % s)

        agency = utils.get_agency(slug)
        if not agency:
            return self.error(404)
        
        crawl_urls = model.CrawlBaseUrl.all().filter('agency =', agency).fetch(100)
        
        self.render('templates/agency_edit.html', {'agency':agency, 'crawl_urls': crawl_urls})

    @app.basic.login_required
    def post(self, slug):
        agency = utils.get_agency(slug)
        if not agency:
            return self.error(404)

        if self.request.POST.get('action.save.url'):
            url = self.request.POST.get('orig_url')
            if url:
                c = model.CrawlBaseUrl().all().filter('url =', url).get()
            else:
                c = model.CrawlBaseUrl()
                c.lastcrawled = datetime.datetime.now()-datetime.timedelta(days=365)
                c.agency = agency
            c.url = self.request.POST.get('url')
            c.recurse = int(self.request.POST.get('recurse'))
            c.download_as = self.request.POST.get('download_as', 'gtfs-archiver')
            c.show_url = self.request.POST.get('show_url', True) == 'True'
            c.post_text = self.request.POST.get('post_text', '')
            c.put()
            self.redirect('/a/edit/' + agency.slug)
            

        # agency.name = self.request.POST.get('name', agency.name)
        # agency.slug = self.request.POST.get('slug', agency.slug)
        agency.description = self.request.POST.get('description', agency.description)
        agency.url = self.request.POST.get('url', agency.url)

        agency.country_name = self.request.POST.get('country', agency.country_name).strip()
        agency.state_name = self.request.POST.get('state', agency.state_name).strip()
        agency.area_name = self.request.POST.get('area', agency.area_name).strip()
        agency.feed_baseurl = self.request.POST.get('feed', agency.feed_baseurl).strip()
        agency.license_url = self.request.POST.get('license', agency.license_url).strip()
        agency.is_official = self.request.POST.get('official', '0') == '1'

        # agency.lastupdate = datetime.datetime.now() # this is for the last message 'update'
        agency.put()
        # memcache.delete('Agency.slug.%s' % slug)
        memcache.delete('Agency.recent')
        memcache.delete('Agency.all')
        memcache.set('Agency.slug.%s' % agency.slug, agency)

        self.render('templates/generic.html', {'message':'Agency %s updated' % agency.name})


class CommentAdminPage(app.basic.BasePublicPage):
    @app.basic.admin_required
    def get(self, key=None):
        if not key:
            return self.error(404)
        try:
            obj = db.get(db.Key(key))
        except:
            return self.error(404)
        if not obj:
            return self.error(404)
        self.render('templates/comment_admin.html', {'msg':obj})
    @app.basic.admin_required
    def post(self, key=None):
        try:
            obj = db.get(db.Key(key))
        except:
            return self.error(404)
        obj.content = self.request.POST.get('comments', obj.content)
        obj.put()
        self.redirect('/meta/%d' % obj.key().id())
