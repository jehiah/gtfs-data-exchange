import base64
import hmac, sys
import hashlib

# NOTE: FOR SOME REASON THIS ISN'T WORKING
# USE http://s3.amazonaws.com/doc/s3-example-code/post/post_sample.html

l = '--local' in sys.argv
params = {
    'url':(l and "http://localhost:8081" or "http://www.gtfs-data-exchange.com"),
    'bucket':(l and 'gtfs-devel' or 'gtfs')
}

policy_document = """
{"expiration": "2012-01-01T00:00:00Z",
  "conditions": [ 
    {"bucket": "%(bucket)s"}, 
    ["starts-with", "$key", "queue/"],
    {"acl": "private"},
    {"success_action_redirect": "%(url)s/queue"},
    ["eq", "$Content-Type", "application/zip"],
    ["content-length-range", 0, 31457280],
    ["starts-with","$x-amz-meta-user",""],
    ["starts-with","$x-amz-meta-comments",""]
    ]
}
""" % params
print policy_document
policy = base64.b64encode(policy_document.strip())

signature = base64.b64encode(hmac.new(AWS_SECRET_ACCESS_KEY, policy, hashlib.sha1).digest())
    
print policy
print "-"*50
print signature
