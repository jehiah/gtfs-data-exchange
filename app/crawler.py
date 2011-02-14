
import datetime
from functools import wraps
from google.appengine.api import users
import tornado.web

import app.basic
import model
import utils
import logging

from app.upload import uploadfile, UploadError

def crawler_required(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        auth = self.request.headers.get('Authorization', None)
        logging.info('auth = ' + str(auth))
        if auth != 'Basic Y3Jhd2xlcjpjcmF3bGVy': ## crawler, crawler
            self.response.headers['WWW-Authenticate'] = 'Basic realm="RESTRICTED ACCESS"'
            raise tornado.web.HTTPError(401)
        return method(self, *args, **kwargs)
    return wrapper


class CrawlerMain(app.basic.BaseController):
    @app.basic.admin_required
    def get(self):
        crawl_urls = model.CrawlBaseUrl.all().order('download_as').fetch(1000)
        self.render('admin_crawler.html', crawl_urls=crawl_urls)
    
    def post(self):
        url = self.get_argument('orig_url')
        if self.get_argument('link'):
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
        c.url = self.get_argument('url')
        c.recurse = int(self.get_argument('recurse'))
        c.download_as = self.get_argument('download_as', 'gtfs-archiver')
        c.show_url = self.get_argument('show_url', True) == 'True'
        c.post_text = self.get_argument('post_text', '')
        c.put()
        self.redirect('/crawl')

class CrawlNextUrl(app.basic.BaseController):
    @crawler_required
    def get(self):
        u = model.CrawlBaseUrl.all().filter('enabled =', True).filter('next_crawl >', datetime.datetime.now()).get()
        if not u:
            return self.response.out.write('NONE')
        logging.debug(str('returning ' + str(u.url) + ' to be cralwed'))
        u.lastcrawled = datetime.datetime.now()
        if u.crawl_interval:
            u.next_crawl = u.lastcrawled + datetime.timedelta(hours=u.crawl_interval)
        else:
            u.next_crawl = u.lastcrawled + datetime.timedelta(hours=24)
        u.put()
        self.response.out.write(str(u.asMapping()))

class CrawlHeaders(app.basic.BaseController):
    @crawler_required
    def get(self):
        url = self.get_argument('url', '')
        c = model.CrawlUrl.all().filter('url =', url).order('-lastseen').get()
        if not c:
            return self.response.out.write('NONE')
        self.response.out.write(c.headers)
    
    @crawler_required
    def post(self):
        url = self.get_argument('url', '')
        c = model.CrawlUrl()
        c.url = url
        c.headers = self.request.POST['headers']
        c.save()
        self.response.out.write('OK')

class CrawlShouldSkip(app.basic.BaseController):
    @crawler_required
    def get(self):
        url = self.get_argument('url', '')
        c= model.CrawlSkipUrl.all().filter('url =', url).get()
        if c:
            c.lastseen = datetime.datetime.now()
            c.put()
            return self.response.out.write('YES')
        self.response.out.write('NO')

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
        
        self.response.out.write('%d %d' % (a, b))

class CrawlUpload(app.basic.BaseController):
    @crawler_required
    def get(self):
        md5sum = self.get_argument('md5sum', '')
        if md5sum and model.Message.all().filter('md5sum =', md5sum).count() >0:
            self.response.out.write('FOUND')
        elif md5sum and model.SkipMd5.all().filter('md5sum =', md5sum).count() >0:
            self.response.out.write('FOUND-skipped')
        else:
            self.response.out.write('NOT_FOUND')
    
    ## don't require crawler here so we don't have to double post
    def post(self):
        ## file is in upload_file
        agencydata = self.get_argument('agencydata')
        comments = self.get_argument('comments')
        username = users.User(self.get_argument('user'))
        md5sum = self.get_argument('md5sum')
        sizeoffile = int(self.get_argument('sizeoffile'))
        try:
            filename = uploadfile(username=username, agencydata=agencydata, comments=comments, md5sum=md5sum, sizeoffile=sizeoffile)
        except UploadError, e:
            return self.response.out.write('ERROR : ' + str(e.msg))
        return self.response.out.write('RENAME:'+filename)
