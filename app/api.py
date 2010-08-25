import app.basic
import utils
import logging
import model

class APIAgencyPage(app.basic.BaseAPIPage):
    def get(self, slug=None):
        if not slug:
            slug = self.request.GET.get('agency', None)
        
        if not slug:
            return self.api_error(404, 'MISSING_ARG_AGENCY')
            
        s = utils.lookup_agency_alias(slug)
        logging.warning('new slug %s '% s)
        if s:
            slug = s
        agency = utils.get_agency(slug)
        logging.warning('agency %s' % agency )
        if not agency:
            return self.api_error(404, 'AGENCY_NOT_FOUND')
        messages =model.MessageAgency.all().filter('agency', agency).order('-date').fetch(1000)
        messages = [message.message.json() for message in messages if message.hasFile]
        self.api_response(dict(
            agency=agency.json(),
            datafiles=messages
        ))


class APIAgencies(app.basic.BaseAPIPage):
    def get(self):
        agencies = utils.get_all_agencies()
        response = [agency.json() for agency in agencies]
        self.api_response(response)

