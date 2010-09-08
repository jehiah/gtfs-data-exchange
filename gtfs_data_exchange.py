import os
import tornado
assert tornado.version_info >= (1,1,0)

import tornado.web
import tornado.wsgi
import wsgiref.handlers

# application imports
import app.admin
import app.agencies
import app.agency
import app.api
import app.basic
import app.crawler
import app.static
import app.upload
import uimethods

class Application(tornado.wsgi.WSGIApplication):
    def __init__(self):
        app_settings = { 
            "template_path": os.path.join(os.path.dirname(__file__), "templates"),
            "debug" : True,
            'ui_methods' : uimethods,
        }
        handlers = [
            (r"/(how-to-provide-open-data)$", app.static.StaticPage),
            (r"/(submit-feed)$", app.static.SubmitFeedPage),
            
            (r"/upload$", app.upload.UploadFile),
            (r"/queue$", app.upload.QueuePage),
            (r"/feed$", app.agency.FeedPage),
            (r"/gtfs/(?P<name>.*\.zip)$", app.upload.ZipFilePage),

            (r"/meta/(?P<key>.*?)/edit/?$", app.admin.CommentAdminPage),
            (r"/meta/(?P<key>.*?)/?$", app.agency.CommentPage),
            (r"/(?P<userOrAgency>user)/(?P<id>.*?)/feed/?$", app.agency.FeedPage),
            (r"/user/(?P<user>.*?)/?$", app.agency.UserPage),
            (r"/(?P<userOrAgency>agency)/(?P<id>.*?)/feed/?$", app.agency.FeedPage),

            (r"/$", app.agencies.MainPage),
            (r"/agency/?$", tornado.web.RedirectHandler, {"url": "/agencies"}),
            (r"/agencies/bylocation$", app.agencies.AgenciesByLocation),
            (r"/agencies/bylastupdate$", app.agencies.AgenciesByLastUpdate),
            (r"/agencies/astable$", app.agencies.AgenciesAsTable),
            (r"/agencies$", app.agencies.Agencies),

            (r"/agency/(?P<slug>.*?).json$", app.api.APIAgencyPage),
            (r"/agency/(?P<slug>.*?)/latest.zip$", app.agency.LatestAgencyFile),
            (r"/agency/(?P<slug>.*?)/?$", app.agency.AgencyPage),
        
            (r"/a/$", app.admin.AdminIndex),
            (r"/a/aliases$", app.admin.AdminAliases),
            (r"/a/edit/(?P<slug>.+)$", app.admin.AgencyEditPage),
        
            (r"/a/crawler$", app.crawler.CrawlerMain),
            (r"/crawl/nexturl$", app.crawler.CrawlNextUrl),
            (r"/crawl/headers$", app.crawler.CrawlHeaders),
            (r"/crawl/shouldSkip$", app.crawler.CrawlShouldSkip),
            (r"/crawl/upload$", app.crawler.CrawlUpload),
            (r"/crawl/undoLastRun$", app.crawler.CrawlUndoLastRun),
        
            (r"^/api/agency$", app.api.APIAgencyPage),
            (r"^/api/agencies$", app.api.APIAgencies),
        ]
        tornado.wsgi.WSGIApplication.__init__(self, handlers, **app_settings)
        
if __name__ == "__main__":
    application = Application()
    wsgiref.handlers.CGIHandler().run(application)
