from google.appengine.api import users
from google.appengine.ext import db
import tornado.web

import logging
import datetime
from django.core.paginator import ObjectPaginator

import app.basic
import model
import utils
import urllib


class CommentPage(app.basic.BasePublicPage):
    def get(self, key=None):
        if not key:
            raise tornado.web.HTTPError(404)
        if not key.isdigit():
            try:
                obj = db.get(db.Key(key))
                return self.redirect('/meta/%d' % obj.key().id())
            except:
                logging.exception('key not found %s' % key)
                raise tornado.web.HTTPError(404)
        
        try:
            obj = model.Message.get_by_id(int(key))
            # obj = db.get(db.Key(key))
        except:
            logging.exception('key not found %s' % key)
            raise tornado.web.HTTPError(404)
        if not obj:
            raise tornado.web.HTTPError(404)
        self.render('comment.html', msg=obj)

class LatestAgencyFile(app.basic.BasePublicPage):
    def get(self, slug):
        s = utils.lookup_agency_alias(slug)
        if s:
            return self.redirect('/agency/%s/' % (s))
        agency = utils.get_agency(slug)
        if not agency:
            raise tornado.web.HTTPError(404)
        message =model.MessageAgency.all().filter('agency', agency).order('-date').fetch(1)
        if message:
            production = self.request.host == 'www.gtfs-data-exchange.com'
            return self.redirect(message[0].message.filelink(production=production))
        raise tornado.web.HTTPError(404)


class AgencyPage(app.basic.BasePublicPage):
    def get(self, slug):
        s = utils.lookup_agency_alias(slug)
        if s:
            return self.redirect('/agency/%s/' % (s))
        
        agency = utils.get_agency(slug)
        if not agency:
            raise tornado.web.HTTPError(404)
        messages =model.MessageAgency.all().filter('agency', agency).order('-date').fetch(1000)

        paginator = ObjectPaginator(messages, 10, 1)
        try:
            page = int(self.get_argument('page', '1'))
        except ValueError:
            page = 1
        if page <= 0:
            page = 1

        try:
            records = paginator.get_page(page-1)
        except:
            records = paginator.get_page(0)
            page = 1

        self.render('agency.html', agency=agency, messages=records, 
                    paginator=paginator,
                    next=paginator.has_next_page(page-1),
                    previous=paginator.has_previous_page(page-1),
                    previous_page_number=page-1,
                    next_page_number=page+1,
                    page=page)


class FeedPage(app.basic.BasePublicPage):
    def get(self, user_or_agency=None, slug=None):
        self.set_header('Content-Type', 'application/atom+xml')
        base_url = self.request.protocol + "://" + self.request.host
        if not user_or_agency:
            messages = model.Message.all().filter('date >', datetime.datetime.now()-datetime.timedelta(90)).order('-date').fetch(15)
            self.render('atom.xml', user_or_agency=user_or_agency, messages=messages, base_url=base_url)
        elif user_or_agency == 'user':
            user = urllib.unquote(slug)
            if '@' in user:
                user = users.User(user)
            else:
                user = users.User(user+'@gmail.com')
            messages = model.Message.all().filter('date >', datetime.datetime.now()-datetime.timedelta(90)).filter('user =', user).order('-date').fetch(15)
            self.render('agency_atom.xml', user_or_agency=user_or_agency, messages=messages, base_url=base_url, user=str(user), agency=None)
        elif user_or_agency == 'agency':
            alias = utils.lookup_agency_alias(slug)
            if alias:
                return self.redirect('/%s/%s/feed' % (user_or_agency, alias))

            agency = model.Agency.all().filter('slug =', slug).get()
            messages = [x.message for x in model.MessageAgency.all().filter('agency =', agency).filter('date >', datetime.datetime.now()-datetime.timedelta(90)).order('-date').fetch(15)]
            self.render('agency_atom.xml', agency=agency, user_or_agency=user_or_agency, messages=messages, base_url=base_url, user='')

class UserPage(app.basic.BasePublicPage):
    def get(self, user):
        import urllib
        user = urllib.unquote(user)
        if '@' in user:
            u = users.User(user)
        else:
            u = users.User(user+'@gmail.com')
        messages= model.Message.all().filter('user =', u).order('-date').fetch(1000)

        if not messages and not users.get_current_user():
            raise tornado.web.HTTPError(404)
        if not messages and users.get_current_user().email() != u.email():
            raise tornado.web.HTTPError(404)

        paginator = ObjectPaginator(messages, 10, 1)
        try:
            page = int(self.get_argument('page', '1'))
        except ValueError:
            page = 1

        try:
            records = paginator.get_page(page-1)
        except:
            records = paginator.get_page(0)
            page = 1
        self.render('user.html', **{'u':u, 'messages':records, 'paginator':paginator,
        "next" : paginator.has_next_page(page-1), 'previous':paginator.has_previous_page(page-1), 'previous_page_number':page-1, 'next_page_number':page+1, "page" : page})
