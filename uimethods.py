from markdown import Markdown
import datetime
       
def markdown(module, value):
    m = Markdown()
    return m.convert(_utf8(value))

def timesince(module, value):
    # TODO: implemnt this
    # logging.info(module, value)
    if not value:
        return ''
    if isinstance(value, datetime.datetime):
        return str(value)
    assert isinstance(value, (str, unicode))
    return value

def filesizeformat(module, value):
    if not value:
        return ''
    return '%d' % value

def _utf8(s):
    if isinstance(s, unicode):
        return s.encode("utf-8")
    assert isinstance(s, str)
    return s
