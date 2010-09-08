from google.appengine.api import users
from google.appengine.ext import db
import tornado.web

import logging
import datetime
from django.core.paginator import ObjectPaginator

import app.basic
import model
import utils


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
            return self.redirect(message[0].message.filelink())
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
        self.render('agency.html', agency=agency, messages=messages)

class FeedPage(app.basic.BasePublicPage):
    def get(self, userOrAgency=None, id=None):
        context = {'userOrAgency':userOrAgency, 'u':id, 'id':id}
        self.response.headers['Content-Type'] = 'application/atom+xml'
        if not userOrAgency:
            context['messages'] = model.Message.all().filter('date >', datetime.datetime.now()-datetime.timedelta(30)).order('-date').fetch(25)
            self.render('atom.xml', context)
        elif userOrAgency == 'user':
            import urllib
            user = urllib.unquote(id)
            if '@' in user:
                u = users.User(user)
            else:
                u = users.User(user+'@gmail.com')
            context['messages'] = model.Message.all().filter('date >', datetime.datetime.now()-datetime.timedelta(30)).filter('user =', u).order('-date').fetch(25)
            self.render('agency_atom.xml', **context)
        elif userOrAgency == 'agency':
            s = utils.lookup_agency_alias(id)
            if s:
                return self.redirect('/%s/%s/feed' % (userOrAgency, s))

            agency = model.Agency.all().filter('slug =', id).get()
            context['agency'] = agency
            context['messages'] = [x.message for x in model.MessageAgency.all().filter('agency =', agency).filter('date >', datetime.datetime.now()-datetime.timedelta(30)).order('-date').fetch(25)]
            self.render('agency_atom.xml', **context)

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

        paginator = ObjectPaginator(messages, 15, 1)
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
