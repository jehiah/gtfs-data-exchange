import base64
import hmac
import hashlib
import tornado.options

# NOTE: FOR SOME REASON THIS ISN'T WORKING
# USE http://s3.amazonaws.com/doc/s3-example-code/post/post_sample.html

def run(bucket, url, aws_secret):
    # l = '--local' in sys.argv
    # params = {
    #     'url':(l and "http://localhost:8081" or "http://www.gtfs-data-exchange.com"),
    #     'bucket':(l and 'gtfs-devel' or 'gtfs')
    # }

    policy_document = """
    {"expiration": "2016-07-01T00:00:00Z",
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
    """ % dict(
        bucket=bucket,
        url=url,
    )
    print policy_document
    policy = base64.b64encode(policy_document.replace('\n','').strip())

    signature = base64.b64encode(hmac.new(aws_secret.encode('utf-8'), policy, hashlib.sha1).digest())
    
    print policy
    print "-"*50
    print signature

if __name__ == "__main__":
    tornado.options.define("bucket", default="gtfs", type=str)
    tornado.options.define("url", default="http://www.gtfs-data-exchange.com", type=str)
    tornado.options.define("aws_secret", type=str)
    tornado.options.parse_command_line()
    
    o = tornado.options.options
    run(o.bucket, o.url, o.aws_secret)

    