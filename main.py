#!/usr/bin/env python

import wsgiref.handlers
from google.appengine.ext.webapp import template

import webapp as webapp2

# app imports
import app.agencies
import app.agency
import app.basic
import app.crawler
import app.upload
import app.admin
import app.api
import app.static

def main():
    application = webapp2.WSGIApplication2(
                  [
                  #('/sitemap.xml', Sitemap),
                   ('/', app.agencies.MainPage),
                   ('/(how-to-provide-open-data)', app.static.StaticPage),
                   ('/(submit-feed)', app.static.SubmitFeedPage),
                   ('/upload', app.upload.UploadFile),
                   ('/queue', app.upload.QueuePage),
                   ('/feed', app.agency.FeedPage),
                   ('/meta/(?P<key>.*?)/edit/?', app.admin.CommentAdminPage),
                   ('/meta/(?P<key>.*?)/?', app.agency.CommentPage),
                   ('/(?P<userOrAgency>user)/(?P<id>.*?)/feed/?', app.agency.FeedPage),
                   ('/user/(?P<user>.*?)/?', app.agency.UserPage),
                   ('/(?P<userOrAgency>agency)/(?P<id>.*?)/feed/?', app.agency.FeedPage),
                   # ('/agency/', RedirectAgencyList),
                   ('/agencies/bylocation', app.agencies.AgenciesByLocation),
                   ('/agencies/bylastupdate', app.agencies.AgenciesByLastUpdate),
                   ('/agencies/astable', app.agencies.AgenciesAsTable),
                   ('/agencies', app.agencies.Agencies),
                   ('/agency/(?P<slug>.*?).json$', app.api.APIAgencyPage),
                   ('/agency/(?P<slug>.*?)/latest.zip', app.agency.LatestAgencyFile),
                   ('/agency/(?P<slug>.*?)/?', app.agency.AgencyPage),
                   ('/gtfs/(?P<name>.*\.zip)', app.upload.ZipFilePage),
                   
                   (r'/a/$', app.admin.AdminIndex),
                   (r'/a/aliases$', app.admin.AdminAliases),
                   (r'/a/edit/(?P<slug>.+)$', app.admin.AgencyEditPage),
                   
                   ('/a/crawler', app.crawler.CrawlerMain),
                   ('/crawl/nexturl', app.crawler.CrawlNextUrl),
                   ('/crawl/headers', app.crawler.CrawlHeaders),
                   ('/crawl/shouldSkip', app.crawler.CrawlShouldSkip),
                   ('/crawl/upload', app.crawler.CrawlUpload),
                   ('/crawl/undoLastRun', app.crawler.CrawlUndoLastRun),
                   
                   (r'^/api/agency$', app.api.APIAgencyPage),
                   (r'^/api/agencies$', app.api.APIAgencies),
                   ], debug=True)
    wsgiref.handlers.CGIHandler().run(application)

template.register_template_library('common.templatefilters')

if __name__ == '__main__':
    # logging.getLogger().setLevel(logging.info)
    main()


