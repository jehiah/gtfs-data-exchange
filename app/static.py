from google.appengine.api import users
from google.appengine.api import mail

import app.basic

class StaticPage(app.basic.BasePublicPage):
    def get(self, template_name):
        self.render('templates/' + template_name + '.html')

class SubmitFeedPage(StaticPage):
    # get will work automagically
    def post(self, template_name):
        ## send an email; render "thank you"

        feed_location = self.request.POST.get('feed_location')
        if not feed_location:
            return self.render('templates/generic.html', {'error':'Feed Location is required'})

        agency_name = self.request.POST.get('agency_name')
        agency_location = self.request.POST.get('agency_location')
        contact_info = self.request.POST.get('contact_info')
        if users.get_current_user():
            user = users.get_current_user().email()
        else:
            user = ''

        mail.send_mail(sender="Jehiah Czebotar <jehiah@gmail.com>",
                      to="Jehiah Czebotar <jehiah@gmail.com>",
                      subject="New GTFS Feed - %s" % (agency_name or feed_location),
                      body="""
Feed URL: %(feed_location)s
Agency Name: %(agency_name)s
Agency Location: %(agency_location)s
Point of Contact: %(contact_info)s
Logged In User: %(user)s
        """ % {
        'agency_name' : agency_name,
        'agency_location' : agency_location,
        'contact_info' : contact_info,
        'feed_location' : feed_location,
        'user' : user
        })

        self.render('templates/generic.html', {'message':'Thank You For Your Submission'})
