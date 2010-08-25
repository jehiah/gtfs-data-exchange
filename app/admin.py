from google.appengine.ext import db
from google.appengine.api import memcache

import model
import app.basic
import utils

class AdminIndex(app.basic.BaseController):
    @app.basic.admin_required
    def get(self):
        self.render('views/admin_index.html')

class AdminAliases(app.basic.BasePublicPage):
    @app.basic.admin_required
    def __before__(self, *args):
        pass
    
    def get(self):
        agencies = utils.getAllAgencies()
        self.render('views/admin_aliases.html', {'agencies': agencies})
    
    def post(self):
        f = self.request.POST.get('from_agency', '')
        t = self.request.POST.get('to_agency', '')
        if not t or f == t:
            return self.render('views/admin_aliases.html', {'error':'Select an agency to merge from, and one to merge to'})
        
        if not f and  (not self.request.POST.get('to_name', '') or not self.request.POST.get('to_slug', '')):
            return self.render('views/admin_aliases.html', {'error':'new name and slug must be selected when only selecting the "to" agency'})
        
        if f:
            f = db.get(db.Key(f))
        t = db.get(db.Key(t))
        
        if not t or f == t:
            return self.render('views/admin_aliases.html', {'error':'Select an agency to merge from, and one to merge to'})
        
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
        
        self.render('views/generic.html', {'message':'Agency Merged Successfully'})


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
        
        self.render('views/agency_edit.html', {'agency':agency, 'crawl_urls': crawl_urls})

    @app.basic.login_required
    def post(self, slug):
        agency = utils.get_agency(slug)
        if not agency:
            return self.error(404)

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
        # memcache.delete('Agency.recent')
        memcache.delete('Agency.all')
        memcache.set('Agency.slug.%s' % agency.slug, agency)

        self.render('views/generic.html', {'message':'Agency %s updated' % agency.name})
