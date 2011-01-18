from functools import wraps
import wsgiref.handlers
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.ext.db import stats
from google.appengine.api import users
from google.appengine.api import memcache
import webapp as webapp2
import model
import random
import string
import datetime
import logging
import os
import csv
import StringIO

def getAllAgencies():
    agencies = memcache.get('Agency.all')
    if not agencies:
        agencies = model.Agency.all().order('name').fetch(500)
        memcache.set('Agency.all',agencies)
    return agencies

def getRecentAgencies():
    key = 'Agency.recent'
    # recentAgencies = memcache.get(key)
    recentAgencies = None
    if recentAgencies is None:
        recentAgencies = model.Agency.all().order('-date_added').fetch(5)
        # memcache.set(key, recentAgencies)
    return recentAgencies
        
def getRecentMessages():
    recentMessages = memcache.get('Message.recent')
    if recentMessages is None:
        # .filter('date >',datetime.datetime.now()-datetime.timedelta(30))
        recentMessages = model.Message.all().order('-date').fetch(7)
        memcache.set('Message.recent',recentMessages,60*60*48) # 1 day
    return recentMessages


def incrAgencyCount():
    memcache.incr('count.Agency')
    count = model.Counter.all().filter('name=',"Agency").get()
    if count:
        count.count +=1
        count.put()

def decrAgencyCount():
    memcache.decr('count.Agency')
    count = model.Counter.all().filter('name=',"Agency").get()
    if count:
        count.count -=1
        count.put()

def getAgencyCount():
    key = 'count.Agency'
    count = memcache.get(key)
    if count is not None:
        return int(count)
    count = model.Counter.all().filter('name=',"Agency").fetch(1)
    if not count:
        # one time shunt; breaks > x entries
        count = model.Agency.all().count()
        c = model.Counter()
        c.name = "Agency"
        c.count = count
        c.put()
    else:
        count = count[0].count
    memcache.set(key, str(count), 60*60*24*2)
    return count
    
def lookupAgencyAlias(lookupslug):
    lookupslug = lookupslug.strip()
    key ='AgencyAlias.slug.%s' % lookupslug
    a = memcache.get(key)
    if a != None:
        return a
    a = model.AgencyAlias.all().filter('slug =',lookupslug).get()
    if a:
        r = a.real_agency.slug
    else:
        r = False
    memcache.set(key,r)#,60*60*24) # 24 hours?
    return r

def getAgency(slug):
    key = 'Agency.slug.%s' % slug
    agency = memcache.get(key)
    if not agency:
        agency = model.Agency.all().filter('slug =',slug).get()
        if not agency:
            return
        memcache.set(key,agency)
    return agency


# def getGenericObjectCount(kind):
#     key = 'count.%s' % kind
#     count = memcache.get(key)
#     if count:
#         return count
#     global_stat = stats.KindStat.all().filter('kind_name =',kind).get()
#     if not global_stat:
#         return ''
#     count = global_stat.count
#     memcache.set(key,count)
#     return count


def readfile(filecontent):
    logging.debug('file contents : ' + filecontent)
    reader = unicode_csv_reader(StringIO.StringIO(filecontent))
    columns =reader.next()
    o=[]
    for line in reader:
        logging.debug('agency line:' + repr(line))
        d={}
        for i in range(min(len(columns),len(line))):
            d[columns[i].strip()]=line[i] ## strip() is for when agency_name is really " agency_name"
        o.append(d)
    return o

def unicode_csv_reader(unicode_csv_data, dialect=csv.excel, **kwargs):
    # csv.py doesn't do Unicode; encode temporarily as UTF-8:
    csv_reader = csv.reader(utf_8_encoder(unicode_csv_data),
                            dialect=dialect, **kwargs)
    for row in csv_reader:
        # decode UTF-8 back to Unicode, cell by cell:
        yield [unicode(cell, 'utf-8') for cell in row]

def utf_8_encoder(unicode_csv_data):
    for line in unicode_csv_data:
        yield line.encode('utf-8')
