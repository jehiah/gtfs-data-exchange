GTFS Data Exchange
------------------

This is the code that powers [gtfs-data-exchange.com](http://www.gtfs-data-exchange.com/) a site 
designed to help developers and transit agencies efficiently share and retrieve GTFS data

*Contributing*

Have an idea for a feature? fork on [github.com/jehiah/gtfs-data-exchange](http://github.com/jehiah/gtfs-data-exchange) and contribute that feature

See development.txt for steps to get up and running


Development Data
----------------
To dump the dev datastore startup with --clear-datastore

for kind in Counter Agency MessageAgency AgencyAlias CrawlBaseUrl CrawlSkipUrl Message; do
    appcfg.py download_data --application=gtfs-data-exchange --kind=$kind --url=http://gtfs-data-exchange.appspot.com/remote_api --filename=data/$kind
done

for kind in Counter Agency MessageAgency AgencyAlias CrawlBaseUrl CrawlSkipUrl Message; do
    appcfg.py upload_data --application=gtfs-data-exchange --kind=$kind --url=http://127.0.0.1:8080/remote_api --filename=data/$kind
done

rm bulkloader-*