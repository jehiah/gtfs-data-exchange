from google.appengine.api import users

import tornado.web
import logging

import csv
import cStringIO

from functools import wraps

def login_required(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self.current_user:
            self.redirect(self.get_login_url())
        else:
            return method(self, *args, **kwargs)
    return wrapper


def admin_required(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self.current_user:
            self.redirect(self.get_login_url())
        elif not users.is_current_user_admin():
            raise tornado.web.HTTPError(403)
        else:
            return method(self, *args, **kwargs)
    return wrapper

class BaseController(tornado.web.RequestHandler):
    def head(self):
        self.set_header("Allow", "GET")
        raise tornado.web.HTTPError(405)
    
    def get_login_url(self):
        return users.create_login_url(self.request.full_url())
    
    def get_current_user(self):
        return users.get_current_user()
    
    def render_string(self, template_name, **kwargs):
        args = dict(
            sign_in_out_url = self.current_user and  users.create_logout_url(self.request.full_url()) or users.create_login_url(self.request.full_url()),
            sign_in_out_text = self.current_user and 'Sign Out' or 'Sign In',
            production = self.request.host == 'www.gtfs-data-exchange.com',
            current_user_is_admin = self.current_user and users.is_current_user_admin(),
        )
        args.update(kwargs)
        return super(BaseController, self).render_string(template_name, **args)

class BasePublicPage(BaseController):
    """
    Do all the common public page prep such as nav pages etc
    """

class BaseAPIPage(BaseController):
    def get(self):
        self.api_error(500, "UNKNOWN_ERROR")
    
    def post(self):
        self.api_error(405, "POST_NOT_SUPPORTED")
    
    def api_error(self, status_code, status_txt):
        self.api_response(None, status_code, status_txt)
    
    def api_response(self, data, status_code=200, status_txt="OK"):
        # logging.info('returning %s' % data)

        if self.get_argument('format', None) == 'csv':
            assert isinstance(data, (list, tuple))
            buffer = cStringIO.StringIO()
            csvwriter = csv.writer(buffer)
            headers = [_utf8(x) for x in data[0].keys()]
            csvwriter.writerow(headers)
            for row in data:
                # be sure to output data in the same order as the headers
                row_data = [_utf8(unicode(row[key])) for key in headers]
                csvwriter.writerow(row_data)
            self.set_header("Content-type", 'text/csv')
            self.finish(buffer.getvalue())
            return
            
        response = dict(status_code=status_code, status_txt=status_txt, data=data)
        callback = self.get_argument('callback', None)
        if callback:
            self.set_header("Content-type", 'application/jsonp')
            self.write(callback+'(')
            self.write(response)
            self.finish(')')
        else:
            self.set_header("Content-type", 'application/javascript')
            self.finish(response)

def _utf8(value):
    if value is None:
        return value
    if isinstance(value, unicode):
        return value.encode("utf-8")
    assert isinstance(value, str)
    return value
