import webapp as webapp2
from google.appengine.ext.webapp import template
from google.appengine.api import users
from django.utils import simplejson as json
import os
import logging
import csv
import cStringIO

from functools import wraps

def login_required(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return
        else:
            return method(self, *args, **kwargs)
    return wrapper


def admin_required(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return
        elif not users.is_current_user_admin():
            return self.error(403)
        else:
            return method(self, *args, **kwargs)
    return wrapper

class BaseController(webapp2.RequestHandler):
    def __init__(self):
        current_userisadmin = False
        if users.get_current_user() and users.is_current_user_admin():
            current_userisadmin = True
        self.template_vals = { 'current_userisadmin':current_userisadmin}
    
    # def __before__(self, *args):
    #     pass
    #
    # def __after__(self, *args):
    #     pass
    def head(self):
        self.response.headers['Allow'] = 'GET'
        return self.error(405)
    
    def errorb(self, errorcode, message='an error occured'):
        if errorcode == 404:
            message = 'Sorry, we were not able to find the requested page.  We have logged this error and will look into it.'
        elif errorcode == 403:
            message = 'Sorry, that page is reserved for administrators.  '
        elif errorcode == 500:
            message = "Sorry, the server encountered an error.  We have logged this error and will look into it."
        return self.render('templates/error.html', {'message':message})
    
    def render(self, template_file, template_vals={}):
        """
        Helper method to render the appropriate template
        """
        if users.get_current_user():
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
        self.production = self.request.url.find('www.gtfs-data-exchange.com')!= -1
        template_vals.update({'url':url,
                             'url_linktext':url_linktext,
                             'user':users.get_current_user(),
                             'production':self.production})
        template_vals.update(self.template_vals)
        path = os.path.join(os.path.join(os.path.dirname(__file__), '..'), template_file)
        self.response.out.write(template.render(path, template_vals))


class BasePublicPage(BaseController):
    """
    Do all the common public page prep such as nav pages etc
    """
    def __before__(self, *args):
        self.production = self.request.url.find('www.gtfs-data-exchange.com')!= -1
        self.template_vals.update({'baseurl':self.request.url[:self.request.url.find('/', 7)]})

class BaseAPIPage(webapp2.RequestHandler):
    def head(self):
        self.response.headers['Allow'] = 'GET'
        return self.error(405)
    
    def get(self):
        self.api_error(500, "UNKNOWN_ERROR")
    
    def post(self):
        self.api_error(405, "POST_NOT_SUPPORTED")
    
    def api_error(self, status_code, status_txt):
        self.api_response(None, status_code, status_txt)
    
    def api_response(self, data, status_code=200, status_txt="OK"):
        # logging.info('returning %s' % data)

        if self.request.GET.get('format', None) == 'csv':
            assert isinstance(data, (list, tuple))
            buffer = cStringIO.StringIO()
            csvwriter = csv.writer(buffer)
            headers = [_utf8(x) for x in data[0].keys()]
            csvwriter.writerow(headers)
            for row in data:
                # be sure to output data in the same order as the headers
                row_data = [_utf8(unicode(row[key])) for key in headers]
                csvwriter.writerow(row_data)
            self.response.headers['Content-type'] = 'text/csv'
            self.response.out.write(buffer.getvalue())
            return
            
        out_data = {
            'status_code':status_code,
            'status_txt':status_txt,
            'data':data
        }
        callback = self.request.GET.get('callback', None)
        if callback:
            self.response.headers['Content-type'] = 'application/jsonp'
            self.response.out.write(callback+'(')
            self.response.out.write(json.dumps(out_data))
            self.response.out.write(')')
        else:
            self.response.headers['Content-type'] = 'application/javascript'
            self.response.out.write(json.dumps(out_data))

def _utf8(value):
    if value is None:
        return value
    if isinstance(value, unicode):
        return value.encode("utf-8")
    assert isinstance(value, str)
    return value
