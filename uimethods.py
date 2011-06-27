from markdown import Markdown
import datetime

def markdown(module, value):
    m = Markdown()
    return m.convert(_utf8(value))

def timesince(module, time_val):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    # modified from http://stackoverflow.com/questions/1551382/python-user-friendly-time-format

    if time_val and time_val == -1:
        return "A long time ago"

    now = datetime.datetime.now()
    if isinstance(time_val, int):
        diff = now - datetime.datetime.fromtimestamp(time_val)
    elif isinstance(time_val, datetime.datetime):
        diff = now - time_val
    elif not time_val:
        diff = now - now
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return str(second_diff) + " seconds ago"
        if second_diff < 120:
            return  "a minute ago"
        if second_diff < 3600:
            return str( second_diff / 60 ) + " minutes ago"
        if second_diff < 7200:
            return "an hour ago"
        if second_diff < 86400:
            return str( second_diff / 3600 ) + " hours ago"
    if day_diff == 1:
        return "Yesterday"
    if day_diff < 7:
        return str(day_diff) + " days ago"
    if day_diff < 31:
        if int(day_diff/7) != 1:
            return str(day_diff/7) + " weeks ago"
        else:
            return "1 week ago"
    if day_diff < 365:
        if int(day_diff/30) != 1:
            return str(day_diff/30) + " months ago"
        else:
            return "1 month ago"
    if int(day_diff/365) == 1:
        return "1 year ago"
    return str(day_diff/365) + " years ago"

        
def filesizeformat(module, value):
    if not value:
        return ''
    return '%d' % value

def _utf8(s):
    if isinstance(s, unicode):
        return s.encode("utf-8")
    assert isinstance(s, str)
    return s
