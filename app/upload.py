from google.appengine.api import memcache

import datetime
import logging
import urlparse

import tornado.web
import app.basic
import model
import utils

class UploadError(Exception):
    def __init__(self, msg):
        logging.warning('upload error ' + str(msg))
        self.msg = msg
    def __str__(self):
        return str(self.msg)


def uploadfile(username, agencydata, comments, md5sum, sizeoffile, bounds):
    ## todo: cache
    if model.Message.all().filter('md5sum =', md5sum).count() >0:
        raise UploadError('This file has previously been uploaded')
    ## todo: cache
    if model.SkipMd5.all().filter('md5sum =', md5sum).count() >0:
        raise UploadError('This file has previously been uploaded')
    
    raw_agencies = utils.readfile(agencydata)
    if not raw_agencies:
        raise UploadError("zip file did not contain any valid agencies in agency.txt.")
    
    ## save our msg
    new_message = model.Message(user=username, content=comments)
    new_message.hasFile = True
    memcache.delete('Message.recent')
    # new_message.filename = filename
    new_message.md5sum = md5sum
    new_message.size = sizeoffile
    new_message.max_lat = None
    new_message.max_lng = None
    new_message.min_lat = None
    new_message.min_lng = None

    if bounds:
        bounds_list = bounds.split("|")
        try:
            new_message.max_lat = float(bounds_list[0])
            new_message.max_lng = float(bounds_list[1])
            new_message.min_lat = float(bounds_list[2])
            new_message.min_lng = float(bounds_list[3])
        except ValueError:
            logging.error('failed to set bounds from %s' % bounds)
            
    new_message.put()
    
    d = datetime.datetime.now()
    datestr = d.strftime('%Y%m%d_%H%M')
    seen_agencies = []
    for ag in raw_agencies:
        ## get from the db
        ## lookup by url first
        
        a = None
        if ag.get('agency_url', '').strip():
            ## try to get via url first as it's more unique
            url = ag['agency_url'].strip()
            try:
                # TODO: use urlnorm
                url_parsed = urlparse.urlparse(url)
                if not url_parsed.path:
                    url += '/'
            except:
                logging.exception('unable to parse url')
            
            a = model.Agency.all().filter('url =', url).get()
        if not a:
            slug = model.slugify(ag['agency_name'].strip())
            s = utils.lookup_agency_alias(slug)
            if s:
                slug = s
            a = memcache.get('Agency.slug.%s' % slug)
            if not a:
                a = model.Agency.all().filter('slug =', slug).get()
        if a:
            a.messagecount +=1
            a.lastupdate = datetime.datetime.now()
            a.put()
            memcache.set('Agency.slug.%s' % a.slug, a)
        if not a:
            a = model.Agency()
            a.name = ag['agency_name'].strip()
            a.url = ag.get('agency_url', '')
            a.messagecount = 1
            a.put()
            memcache.delete('Agency.recent')
            utils.incrAgencyCount()
        
        if len(raw_agencies) == 1:
            new_message.filename = '%s_%s.zip' % (a.slug, datestr)
            new_message.put()
        
        # some zip files have the same url several times; only capture the first time that url is used
        if a in seen_agencies:
            continue
        seen_agencies.append(a)
        
        ma= model.MessageAgency()
        ma.agency = a
        ma.message = new_message
        ma.hasFile=True
        ma.put()
        memcache.delete('Agency.all') # because it has the cached last-update
    
    if not new_message.filename:
        new_message.filename = '%s_%s.zip' % (username.nickname(), datestr)
        new_message.put()
    
    # TODO: can we even hit this, since upload should only be called at a rate of once a minute anyway?
    recentFiles = model.Message.all().filter('hasFile =', True).filter('date >=', d.replace(second=0, microsecond=0)).count()
    if recentFiles > 1: # note we already saved *this* filename
        new_message.filename = new_message.filename.replace('.zip', '_%d.zip' % recentFiles)
        new_message.put()
    
    ## send email to user ?
    
    return new_message.filename

class UploadFile(app.basic.BasePublicPage):
    def get(self):
        self.redirect("https://transit.land/feed-registry/")
    
class QueuePage(app.basic.BasePublicPage):
    def get(self):
        if not self.get_argument('key', '') or not self.get_argument('bucket', '').startswith('gtfs'):
            return self.redirect('/upload')
        self.render('queue.html')

class ZipFilePage(app.basic.BasePublicPage):
    def __before__(self, *args):
        pass
    
    def get(self, name):
        key = 'DataFile.name.%s' % name
        message = memcache.get(key)
        if not message:
            message = model.Message.all().filter('filename =', name).get()
            memcache.set(key, message)
        production = not self.settings['debug']
        
        if message:
            redirect_url = message.filelink(production=production)
            logging.info('redirecting to file at %s' % redirect_url)
            return self.redirect(redirect_url)
        else:
            raise tornado.web.HTTPError(404)
