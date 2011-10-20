
import datetime
from functools import wraps
from google.appengine.api import users
from google.appengine.api import memcache
import tornado.web

import app.basic
import model
import utils
import logging
import hashlib

from app.upload import uploadfile, UploadError


def crawler_required(method):
    """Verify access against the CrawlerTokens table. any token that is present is sufficient to grant access"""
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        auth = self.request.headers.get('X-Crawler-Token', None)
        if not auth:
            logging.warning('missing auth header')
            raise tornado.web.HTTPError(403)
        
        logging.info('lookup up X-Crawler-Token=%s' % auth)
        token = memcache.get('CrawlerToken.%s' % auth)
        if not token:
            token = model.CrawlerToken().all().filter('token =', auth).get()
            memcache.set('CrawlerToken.%s' % auth, token and '1' or '-')
        if not token or token == '-':
            logging.info('no token found for %r' % auth)
            raise tornado.web.HTTPError(403)
        return method(self, *args, **kwargs)
    return wrapper

class CrawlerTokens(app.basic.BaseController):
    @app.basic.admin_required
    def get(self):
        tokens = model.CrawlerToken.all().fetch(50)
        self.render('admin_crawler_tokens.html', tokens=tokens)
    
    @app.basic.admin_required
    def post(self):
        token = model.CrawlerToken()
        token.token = hashlib.sha1(str(datetime.datetime)).hexdigest()
        token.put()
        self.redirect('/a/crawler_tokens')

class CrawlerMain(app.basic.BaseController):
    @app.basic.admin_required
    def get(self):
        crawl_urls = model.CrawlBaseUrl.all().order('download_as').fetch(1000)

        new_crawl = model.CrawlBaseUrl()
        new_crawl.lastcrawled = datetime.datetime.now()-datetime.timedelta(days=365)
        new_crawl.next_crawl = datetime.datetime.now() + datetime.timedelta(minutes=10)
        new_crawl.enabled = False

        self.render('admin_crawler.html', crawl_urls=crawl_urls, crawl_url=new_crawl)
    
    def post(self):
        url = self.get_argument('orig_url', None)
        if self.get_argument('link', None):
            # link this to an agency
            agency = utils.get_agency(self.get_argument('link'))
            c = model.CrawlBaseUrl().all().filter('url =', url).get()
            c.agency = agency
            c.put()
            return self.redirect('/a/edit/' + agency.slug)
        
        if url:
            c = model.CrawlBaseUrl().all().filter('url =', url).get()
        else:
            c = model.CrawlBaseUrl()
            c.lastcrawled = datetime.datetime.now()-datetime.timedelta(days=365)
            c.next_crawl = datetime.datetime.now() + datetime.timedelta(minutes=10)
            c.enabled = True
        c.url = self.get_argument('url')
        c.recurse = int(self.get_argument('recurse'))
        c.download_as = self.get_argument('download_as', 'gtfs-archiver')
        c.show_url = self.get_argument('show_url', True) == 'True'
        c.post_text = self.get_argument('post_text', '')
        c.crawl_interval = int(self.get_argument('crawl_interval', 24))
        c.put()
        self.redirect('/a/crawler')

class CrawlerEdit(app.basic.BaseController):
    @app.basic.admin_required
    def get(self, archiver):
        logging.info('getting crawler urls for %s' % archiver)
        crawl_urls = utils.get_archiver_crawler_urls(archiver)
        if not crawl_urls:
            raise tornado.web.HTTPError(404)
        self.render('crawler_edit.html', archiver=archiver, crawl_urls=crawl_urls, error=None)
    
    @app.basic.admin_required
    def post(self, archiver):
        if self.get_argument('action.enable', None):
            url = self.get_argument('orig_url')
            c = model.CrawlBaseUrl().all().filter('url =', url).get()
            c.enabled = True
            c.put()
            return self.redirect('/a/crawler/' + c.download_as)
        
        elif self.get_argument('action.disable', None):
            url = self.get_argument('orig_url')
            c = model.CrawlBaseUrl().all().filter('url =', url).get()
            c.enabled = False
            c.put()
            return self.redirect('/a/crawler/' + c.download_as)
        elif self.get_argument('action.requeue', None):
            url = self.get_argument('orig_url')
            c = model.CrawlBaseUrl().all().filter('url =', url).get()
            c.next_crawl=datetime.datetime.now()
            c.put()
            return self.redirect('/a/crawler/' + c.download_as)
        
        
        url = self.get_argument('orig_url', '')
        if url:
            c = model.CrawlBaseUrl().all().filter('url =', url).get()
        else:
            c = model.CrawlBaseUrl()
            c.lastcrawled = datetime.datetime.now()-datetime.timedelta(days=365)
            c.next_crawl = datetime.datetime.now() + datetime.timedelta(minutes=10)
            # c.agency = agency
        c.url = self.get_argument('url')
        c.recurse = int(self.get_argument('recurse'))
        c.crawl_interval = int(self.get_argument('crawl_interval', 24))
        c.download_as = self.get_argument('download_as', 'gtfs-archiver')
        c.show_url = self.get_argument('show_url', True) == 'True'
        c.post_text = self.get_argument('post_text', '')
        c.put()
        return self.redirect('/a/crawler/' + c.download_as)


class CrawlNextUrl(app.basic.BaseController):
    @crawler_required
    def get(self):
        u = model.CrawlBaseUrl.all().filter('enabled =', True).filter('next_crawl <', datetime.datetime.now()).get()
        if not u:
            logging.info('no URLs to be crawled')
            return self.finish('NONE')
        logging.debug('returning %r to be cralwed' % u.url)
        u.lastcrawled = datetime.datetime.now()
        if u.crawl_interval:
            u.next_crawl = u.lastcrawled + datetime.timedelta(hours=u.crawl_interval)
        else:
            u.next_crawl = u.lastcrawled + datetime.timedelta(hours=24)
        u.put()
        self.finish(u.asMapping())

class CrawlHeaders(app.basic.BaseController):
    @crawler_required
    def get(self):
        url = self.get_argument('url', '')
        c = model.CrawlUrl.all().filter('url =', url).order('-lastseen').get()
        if not c:
            return self.finish('NONE')
        self.finish(c.headers)
    
    @crawler_required
    def post(self):
        url = self.get_argument('url', '')
        c = model.CrawlUrl()
        c.url = url
        c.headers = self.get_argument('headers')
        c.save()
        self.finish('OK')

class CrawlShouldSkip(app.basic.BaseController):
    @crawler_required
    def get(self):
        url = self.get_argument('url', '')
        c= model.CrawlSkipUrl.all().filter('url =', url).get()
        if c:
            c.lastseen = datetime.datetime.now()
            c.put()
            return self.finish('YES')
        self.finish('NO')

class CrawlUndoLastRun(app.basic.BaseController):
    @crawler_required
    def post(self):
        t = datetime.datetime.now()-datetime.timedelta(hours=12)
        a=0
        b=0
        for c in model.CrawlBaseUrl.all().filter('lastcrawled >=', t).fetch(500):
            a+=1
            c.lastcrawled -= datetime.timedelta(hours=24)
            c.put()
        
        ## now get delete the headers that were saved
        for u in model.CrawlUrl.all().filter('lastseen >=', t).fetch(1000):
            b +=1
            u.delete()
        
        self.finish('%d %d' % (a, b))

class CrawlUpload(app.basic.BaseController):
    @crawler_required
    def get(self):
        md5sum = self.get_argument('md5sum', '')
        if md5sum and model.Message.all().filter('md5sum =', md5sum).count() >0:
            self.finish('FOUND')
        elif md5sum and model.SkipMd5.all().filter('md5sum =', md5sum).count() >0:
            self.finish('FOUND-skipped')
        else:
            self.finish('NOT_FOUND')
    
    ## don't require crawler here so we don't have to double post
    def post(self):
        ## file is in upload_file
        agencydata = self.get_argument('agencydata')
        comments = self.get_argument('comments')
        username = users.User(self.get_argument('user'))
        md5sum = self.get_argument('md5sum')
        sizeoffile = int(self.get_argument('sizeoffile'))
        bounds = self.get_argument('bounds', None)
        try:
            filename = uploadfile(username=username, agencydata=agencydata, comments=comments, md5sum=md5sum, sizeoffile=sizeoffile, bounds=bounds)
        except UploadError, e:
            return self.finish('ERROR : ' + str(e.msg))
        return self.finish('RENAME:'+filename)
