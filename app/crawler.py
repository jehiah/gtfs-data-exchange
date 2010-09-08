
import datetime
from functools import wraps
from google.appengine.api import users

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
            return self.error(401)
        return method(self, *args, **kwargs)
    return wrapper


class CrawlerMain(app.basic.BaseController):
    @app.basic.admin_required
    def get(self):
        crawlurls = model.CrawlBaseUrl.all().order('lastcrawled').fetch(1000)
        crawlurls = [x for x in crawlurls if not x.agency] # filter out the ones linked to an agency since we can't do that in a filter()
        agencies = utils.get_all_agencies()
        self.render('templates/crawler_main.html', {'crawlurls':crawlurls, 'agencies':agencies})
    
    def post(self):
        url = self.request.POST.get('orig_url')
        if self.request.POST.get('link'):
            # link this to an agency
            agency = utils.get_agency(self.request.POST.get('link'))
            c = model.CrawlBaseUrl().all().filter('url =', url).get()
            c.agency = agency
            c.put()
            return self.redirect('/a/edit/' + agency.slug)
        
        if url:
            c = model.CrawlBaseUrl().all().filter('url =', url).get()
        else:
            c = model.CrawlBaseUrl()
            c.lastcrawled = datetime.datetime.now()-datetime.timedelta(days=365)
        c.url = self.request.POST.get('url')
        c.recurse = int(self.request.POST.get('recurse'))
        c.download_as = self.request.POST.get('download_as', 'gtfs-archiver')
        c.show_url = self.request.POST.get('show_url', True) == 'True'
        c.post_text = self.request.POST.get('post_text', '')
        c.put()
        self.redirect('/crawl')

class CrawlNextUrl(app.basic.BaseController):
    @crawler_required
    def get(self):
        if self.request.GET.get('timeframe', ''):
            d = datetime.datetime.now() - datetime.timedelta(minutes=30)
        else:
            d = datetime.datetime.now() - datetime.timedelta(hours=12)
        #d = datetime.datetime.now() + datetime.timedelta(hours=1)
        u = model.CrawlBaseUrl.all().filter('lastcrawled <', d).order('-lastcrawled').get()
        if not u:
            return self.response.out.write('NONE')
        logging.debug(str('returning ' + str(u.url) + ' to be cralwed'))
        u.lastcrawled = datetime.datetime.now()
        u.put()
        self.response.out.write(str(u.asMapping()))

class CrawlHeaders(app.basic.BaseController):
    @crawler_required
    def get(self):
        url = self.request.GET.get('url', '')
        c = model.CrawlUrl.all().filter('url =', url).order('-lastseen').get()
        if not c:
            return self.response.out.write('NONE')
        self.response.out.write(c.headers)
    
    @crawler_required
    def post(self):
        url = self.request.POST.get('url', '')
        c = model.CrawlUrl()
        c.url = url
        c.headers = self.request.POST['headers']
        c.save()
        self.response.out.write('OK')

class CrawlShouldSkip(app.basic.BaseController):
    @crawler_required
    def get(self):
        url = self.request.GET.get('url', '')
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
        md5sum = self.request.GET.get('md5sum', '')
        if md5sum and model.Message.all().filter('md5sum =', md5sum).count() >0:
            self.response.out.write('FOUND')
        elif md5sum and model.SkipMd5.all().filter('md5sum =', md5sum).count() >0:
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
            filename = uploadfile(username=username, agencydata=agencydata, comments=comments, md5sum=md5sum, sizeoffile=sizeoffile)
        except UploadError, e:
            return self.response.out.write('ERROR : ' + str(e.msg))
        return self.response.out.write('RENAME:'+filename)
