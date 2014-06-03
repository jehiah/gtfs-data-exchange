import base64
import tornado.options
import hashlib
import hmac
import json
import pprint

def run(policy, aws_secret_key, expiration):
    raw_policy = json.loads(base64.b64decode(policy))
    print "current policy:"
    pprint.pprint(raw_policy)
    raw_policy['expiration'] = expiration
    policy = base64.b64encode(json.dumps(raw_policy))
    signature = base64.b64encode(hmac.new(aws_secret_key, policy, hashlib.sha1).digest())
    print "policy = %r" % policy
    print "signature = %r" % signature

if __name__ == "__main__":
    tornado.options.define("policy", type=str)
    tornado.options.define("aws_secret_key", type=str)
    tornado.options.define("expiration", type=str, default='2015-06-01T00:00:00Z')
    tornado.options.parse_command_line()
    o = tornado.options.options
    run(o.policy, o.aws_secret_key, o.expiration)

