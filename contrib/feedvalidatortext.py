#!/Library/Frameworks/Python.framework/Versions/2.4/Resources/Python.app/Contents/MacOS/Python

# Copyright (C) 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Validates a Google Transit Feed Specification feed.
#
#
# usage: feedvalidator.py [options] feed_filename
#
# options:
#   --version             show program's version number and exit
#   -h, --help            show this help message and exit
#   -n, --noprompt        do not prompt for feed location or load output in
#                         browser
#   -o FILE, --output=FILE
#                         write html output to FILE

import codecs
import time
import transitfeed
import sys,os

DEFAULT_UNUSED_LIMIT = 5  # number of unused stops to print

def ProblemCountText(error_count, warning_count):
  error_text = ''
  warning_text= ''
  
  if error_count > 1:
    error_text = '%d errors' % error_count
  elif error_count == 1:
    error_text = 'one error'
    
  if warning_count > 1:
    warning_text = '%d warnings' % warning_count
  elif warning_count == 1:
    warning_text = 'one warning'
  
  # Add a way to jump to the warning section when it's useful  
  if error_count and warning_count:
    warning_text = '%s' % warning_text
    
  results = []
  if error_text:
    results.append(error_text)
  if warning_text:
    results.append(warning_text)
    
  return ' and '.join(results)

class TEXTCountingProblemReporter(transitfeed.ProblemReporter):
  def __init__(self):
    transitfeed.ProblemReporter.__init__(self)
    self._error_output = []
    self._warning_output = []
    self.error_count = 0
    self.warning_count = 0
    self.unused_stops = []  # [(stop_id, stop_name)...]

  def HasIssues(self):
    return self.error_count or self.warning_count

  def UnusedStop(self, stop_id, stop_name):
    self.warning_count += 1
    self.unused_stops.append((stop_id, stop_name))

  def _Report(self, e):
    if e.IsWarning():
      self.warning_count += 1
      output = self._warning_output
    else:
      self.error_count += 1
      output = self._error_output
    d = e.GetDictToFormat()
    for k in ('file_name', 'feedname', 'column_name'):
      if k in d.keys():
        d[k] = '<code>%s</code>' % d[k]
    problem_text = e.FormatProblem(d).replace('\n', '<br>')
    output.append('<li>')
    output.append('<div class="problem">%s</div>' %
                  transitfeed.EncodeUnicode(problem_text))
    try:
      output.append('in line %d of <code>%s</code><br>\n' %
                    (e.row_num, e.file_name))
      row = e.row
      headers = e.headers
      column_name = e.column_name
      table_header = ''  # HTML
      table_data = ''  # HTML
      for header, value in zip(headers, row):
        attributes = ''
        if header == column_name:
          attributes = ' class="problem"'
        table_header += '<th%s>%s</th>' % (attributes, header)
        table_data += '<td%s>%s</td>' % (attributes, value)
      output.append('<table><tr>%s</tr>\n' % table_header)
      # Make sure output contains strings with UTF-8 or binary data, not unicode
      output.append('<tr>%s</tr></table>\n' %
                    transitfeed.EncodeUnicode(table_data))
    except AttributeError, e:
      pass  # Hope this was getting an attribute from e ;-)
    output.append('<br></li>\n')

  def _UnusedStopSection(self):
    unused = []
    unused_count = len(self.unused_stops)
    if unused_count:
      if unused_count == 1:
        unused.append('%d.<br>' % self.warning_count)
        unused.append('<div class="unused">')
        unused.append('one stop was found that wasn\'t')
      else:
        unused.append('%d&ndash;%d.<br>' %
                      (self.warning_count - unused_count + 1,
                       self.warning_count))
        unused.append('<div class="unused">')
        unused.append('%d stops were found that weren\'t' % unused_count)
      unused.append(' used in any trips')
      if unused_count > DEFAULT_UNUSED_LIMIT:
        self.unused_stops = self.unused_stops[:DEFAULT_UNUSED_LIMIT]
        unused.append(' (the first %d are shown below)' %
                      len(self.unused_stops))
      unused.append(':<br>')
      unused.append('<table><tr><th>stop_name</th><th>stop_id</th></tr>')
      for stop_id, stop_name in self.unused_stops:
        unused.append('<tr><td>%s</td><td>%s</td></tr>' % (stop_name, stop_id))
      unused.append('</table><br>')
      unused.append('</div>')
    return ''.join(unused)

  def WriteOutput(self, feed_location, f, schedule, problems):
    """return the text output to f."""
    if problems.HasIssues():
      summary = ('<strong>Validation Results:</strong> %s found' %
                 ProblemCountText(problems.error_count, problems.warning_count))
    else:
      summary = '<strong>Validated Successfully</strong>'

    basename = os.path.basename(feed_location)
    feed_path = (feed_location[:feed_location.rfind(basename)], basename)


    dates = "No valid service dates found"
    (start, end) = schedule.GetDateRange()
    if start and end:
      src_format = "%Y%m%d"
      dst_format = "%B %d, %Y"
      formatted_start = time.strftime(dst_format,
                                      time.strptime(start, src_format))
      formatted_end = time.strftime(dst_format, time.strptime(end, src_format))
      dates = "%s to %s" % (formatted_start, formatted_end)

    output= """
<div class="validationresults">
<p>%(summary)s</p>

<table>
<tr><th>Agencies:</th><td>%(agencies)s</td></tr>
<tr><th>Routes:</th><td>%(routes)s</td></tr>
<tr><th>Stops:</th><td>%(stops)s</td></tr>
<tr><th>Trips:</th><td>%(trips)s</td></tr>
<tr><th>Shapes:</th><td>%(shapes)s</td></tr>
<tr><th>Effective:</th><td>%(dates)s</td></tr>
</table>

<p class="validatedby">validated by <a href="http://code.google.com/p/googletransitdatafeed/wiki/FeedValidator">
FeedValidator</a> version %(version)s</p>
</div>
""" % { "feed_file": feed_path[1],
            "feed_dir": feed_path[0],
            "agencies": len(schedule.GetAgencyList()),
            "routes": len(schedule.GetRouteList()),
            "stops": len(schedule.GetStopList()),
            "trips": len(schedule.GetTripList()),
            "shapes": len(schedule.GetShapeList()),
            "dates": dates,
            "summary": summary,
            "version":transitfeed.__version__ }
    if '--debug' in sys.argv:
        if self._error_output:
            output +='<h3 class="issueHeader">Errors:</h3><ol>'
            for line in self._error_output:
                output +=  line
            output += '</ol>'
        if self._warning_output:
            output +='<a name="warnings"><h3 class="issueHeader">Warnings:</h3></a><ol>'
            for line in self._warning_output:
                output += line
            output += '</ol>'
    return output

    

def main(feed):
  problems = TEXTCountingProblemReporter()
  loader = transitfeed.Loader(feed, problems=problems, extra_validation=True,
                              memory_db=False)
  schedule = loader.Load()
  return problems.WriteOutput(os.path.abspath(feed), '', schedule, problems)

if __name__ == '__main__':
    print main(sys.argv[-1])

