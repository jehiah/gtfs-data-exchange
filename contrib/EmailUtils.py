import smtplib
import StringIO
import MimeWriter
import markdown
import logging

import tornado.options
tornado.options.define('skip_email', type=bool, default=False, help="skip sending emails")

def sendEmail(toemail, subject, text, fromAddress="jehiah+gtfs-data-exchange@gmail.com"):
    if tornado.options.options.skip_email:
        logging.info('skipping sending email to %r Sub:%r' % (toemail, subject))
        return
    try:
        server = smtplib.SMTP('127.0.0.1')
    except:
        print "failed to connect to mail server"
        return
    m = markdown.Markdown()
    html = str(m.convert(text))
    params=dict(html=html, subject=subject, email=toemail)

    message = StringIO.StringIO()
    writer = MimeWriter.MimeWriter(message)
    writer.addheader('MIME-Version', '1.0')
    writer.addheader('Subject', subject)
    writer.addheader('To','<'+toemail+'>')
    #writer.addheader('Reply-To','"GTFS Data Exchange"<donotreply@'+params["webhost"]+'>')
    writer.addheader('From','"GTFS Data Exchange" <'+fromAddress+'>')
    ## can't set Return-Path because it gets overridden by MTA's with the From address

    body = writer.startmultipartbody('alternative')

    subpart = writer.nextpart()
    body = subpart.startbody('text/plain;charset="us-ascii"')
    text = """
-----------------------------------------------------
GTFS Developer Exchange
%(subject)s
-----------------------------------------------------
"""+text+"""
-----------------------------------------------------
This is an automated email from GTFS Data Exchange
http://www.gtfs-data-exchange.com/
    """ % params
    body.write(text+"\n")
    subpart = writer.nextpart()
    body=subpart.startbody('text/html;charset="us-ascii"')
    html = '''
<html>
<head>
    <style>
    html,body{background-color:#777;}
    html,td,p,li{font-family:Helvetica;}
    h1{font-family:Helvetica;font-size:11pt;}
    h2{font-family:Helvetica;font-size:10pt;}
    td,p{line-height:1.2}
    li{margin-top:4px;}
    </style>
</head>
<body style="background-color:#777;">
<table width="600" align="center" style="border:1px solid #666;border-width:0px 3px 3px 2px;background-color:#c0c0c0;margin:0 10px 0 10px;" cellpadding="0" cellspacing="0">
    <tr style="background-color:#00a128;" height="75px">
        <td width="19">&nbsp;</td>
        <td width="210"><span style="font-family:Helvetica,Verdana;font-size:11pt;color:#fff;font-weight:bold;">GTFS Data Exchange</span></td>
        <td width="352" align="right" valign="middle" style="text-align:right;"><span style="font-family:Helvetica,Verdana;font-size:11pt;color:#fff;font-weight:bold;">%(subject)s</style></td>
        <td width="19">&nbsp;</td>
    </tr>
    <tr style="background-color:#ffffff;" height="3px"><td colspan="4"></td></tr>

    <tr><td style="font-size:10pt;padding:14px;" colspan="4">
%(html)s
    </td></tr>
    <tr style="background-color:#ffffff;" height="3px"><td colspan="4"></td></tr>
    <tr style="background-color:#00a128;" height="10px"><td colspan="4"></td></tr>
    </table> 

<div style="font-size:8pt;color:#c0c0c0;text-align:center;padding:5px;">
This is an automated email from GTFS Data Exchange, it was sent to (%(email)s)
<http://www.gtfs-data-exchange.com/>
</div>
</body>
</html>
''' % params

    body.write(html)

    writer.lastpart()
    server.sendmail(fromAddress, toemail, message.getvalue())
