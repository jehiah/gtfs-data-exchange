import base64
import hmac, sha,sys
from s3settings import AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY
l = '--local' in sys.argv
params = {
    'url':(l and "http://localhost:8081" or "http://www.gtfs-data-exchange.com"),
    'bucket':(l and 'gtfs-devel' or 'gtfs')
}

policy_document = """
{"expiration": "2011-01-01T00:00:00Z",
  "conditions": [ 
    {"bucket": "%(bucket)s"}, 
    ["starts-with", "$key", "queue/"],
    {"acl": "private"},
    {"success_action_redirect": "%(url)s/queue"},
    ["starts-with", "$Content-Type", ""],
    ["content-length-range", 0, 31457280],
    ["starts-with","$x-amz-meta-user",""],
    ["starts-with","$x-amz-meta-comments",""]
    ]
}
""" % params

policy = base64.b64encode(policy_document)

signature = base64.b64encode(
    hmac.new(AWS_SECRET_ACCESS_KEY, policy, sha).digest())
    
print policy
print "-"*50
print signature
