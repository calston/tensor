import re
from datetime import datetime

class ApacheLogParserError(Exception):
    pass

class ApacheLogParser:
    """Parses Apache log format 

    Adapted from http://code.google.com/p/apachelog

    :param format: Apache log format definition eg
             r'%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"'
             or one of 'common', 'vhcommon' or 'combined'
    :type format: str
    """
    def __init__(self, format):
        formats = {
            # Common Log Format (CLF)
            'common': r'%h %l %u %t \"%r\" %>s %b',

            # Common Log Format with Virtual Host
            'vhcommon': r'%v %h %l %u %t \"%r\" %>s %b',

            # NCSA extended/combined log format
            'combined': r'%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-agent}i\"',
        }

        self._names = []
        self._types = []
        self._regex = None
        self._pattern = ''

        self.types = {
            '%h': ('client', str),
            '%a': ('client-ip', str),
            '%b': ('bytes', int),
            '%B': ('bytes', int),
            '%D': ('request-time', int),
            '%T': ('request-time', float),
            '%f': ('filename', str),
            '%l': ('logname', str),
            '%u': ('user', str),
            '%t': ('time', self._parse_date),
            '%r': ('request', str),
            '%>s': ('status', int),
            '%v': ('vhost', str),
        }

        if format in formats:
            self._parse_format(formats[format])
        else:
            self._parse_format(format)

    def _parse_date(self, date):
        date = date.split()[0][1:]
        return datetime.strptime(date, "%d/%b/%Y:%H:%M:%S")

    def alias(self, field):
        if field in self.types:
            return self.types[field][0]
        else:
            return field
    
    def _parse_format(self, format):
        """
        Converts the input format to a regular
        expression, as well as extracting fields

        Raises an exception if it couldn't compile
        the generated regex.
        """
        format = format.strip()
        format = re.sub('[ \t]+',' ',format)
        
        subpatterns = []

        findquotes = re.compile(r'^\\"')
        findreferreragent = re.compile('Referer|User-Agent')
        findpercent = re.compile('^%.*t$')
        lstripquotes = re.compile(r'^\\"')
        rstripquotes = re.compile(r'\\"$')
        header = re.compile(r'.*%\{([^\}]+)\}i')
        
        for element in format.split(' '):

            hasquotes = 0
            if findquotes.search(element): hasquotes = 1

            if hasquotes:
                element = lstripquotes.sub('', element)
                element = rstripquotes.sub('', element)
            
            head = header.match(element)
            if head:
                self._names.append(head.groups()[0].lower())
                self._types.append(str)
            else:
                self._names.append(self.alias(element))
                self._types.append(self.types.get(element, [None, str])[1])
            
            subpattern = '(\S*)'
            
            if hasquotes:
                if element == '%r' or findreferreragent.search(element):
                    subpattern = r'\"([^"\\]*(?:\\.[^"\\]*)*)\"'
                else:
                    subpattern = r'\"([^\"]*)\"'
                
            elif findpercent.search(element):
                subpattern = r'(\[[^\]]+\])'
                
            elif element == '%U':
                subpattern = '(.+?)'
            
            subpatterns.append(subpattern)
        
        self._pattern = '^' + ' '.join(subpatterns) + '$'
        try:
            self._regex = re.compile(self._pattern)
        except Exception, e:
            raise ApacheLogParserError(e)
        
    def parse(self, line):
        """
        Parses a single line from the log file and returns
        a dictionary of it's contents.

        Raises and exception if it couldn't parse the line
        """
        line = line.strip()
        match = self._regex.match(line)
        
        if match:
            data = {}
            for i, e in enumerate(match.groups()):
                if e == "-":
                    k, v = self._names[i], None
                else:
                    k, v = self._names[i], self._types[i](e)
                data[k] = v
            return data
        
        raise ApacheLogParserError("Unable to parse: %s" % line)

    def pattern(self):
        """
        Returns the compound regular expression the parser extracted
        from the input format (a string)
        """
        return self._pattern

    def names(self):
        """
        Returns the field names the parser extracted from the
        input format (a list)
        """
        return self._names

