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
        ## Get agencies ??
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
