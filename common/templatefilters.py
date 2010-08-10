# import the webapp module
from google.appengine.ext import webapp
from markdown import Markdown
import logging
# get registry, we need it to register our filter later.
register = webapp.template.create_template_register()

def gtfsurl(value,production=None):
    """ truncates a string to a given maximum
        size and appends the stopper if needed """
    if not value:
        return ''
    return value.filelink(production=production)
       
def markdown(value):
    m = Markdown()
    return m.convert(str(value))
    
register.filter(gtfsurl)
register.filter(markdown)
