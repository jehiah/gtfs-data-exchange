import urllib2
import django.utils.simplejson as json

import sys
sys.path.append('/Applications/GoogleAppEngineLauncher.app/Contents/Resources/GoogleAppEngine-default.bundle/Contents/Resources/google_appengine/')

import model
import utils
import datetime

def main():
    # delete existing Agencies
    for aa in model.AgencyAlias.all().fetch(1000):
        print "deleting AgencyAlias"
        aa.delete()
        
    for mm in model.MessageAgency.all().fetch(1000):
        print "deleting Message", mm.message.filelink()
        mm.message.delete()
        mm.delete()
        
    for a in model.Agency.all().fetch(1000):
        print 'deleting Agency', a.slug
        a.delete()
        
    for c in model.Counter.all().filter('name=',"Agency").fetch(10):
        c.delete()
    
    data = urllib2.urlopen('http://www.gtfs-data-exchange.com/api/agencies').read()
    data = json.loads(data)['data']
    for agency in data:
        print "adding",agency
        a = model.Agency()
        a.url = agency['url']
        a.name = agency['name']
        a.slug = agency['dataexchange_url'].split('/')[-2]
        # a.slug = agency['dataexchange_id']
        a.country_name = agency['country']
        a.state_name = agency['state']
        a.area_name = agency['area']
        a.feed_baseurl = agency['feed_baseurl']
        a.license_url = agency['license_url']
        a.is_official = agency.get('is_official',False)
        a.date_added = datetime.datetime.utcfromtimestamp(agency['date_added'])
        a.lastupdate = datetime.datetime.utcfromtimestamp(agency['date_last_updated'])
        a.put()
    
    # TODO: load message data too
    
if __name__ == "__main__":
    main()