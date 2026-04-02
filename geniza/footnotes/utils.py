from html.parser import HTMLParser


class HTMLLineNumberParser(HTMLParser):
    """HTML parser to add numbering and directionality to line elements for search indexing purposes"""

    def __init__(self, *args, **kwargs):
        """Initialize empty string, line numbering at 1, and directionality"""
        self.html_str = ""
        self.line_number = 1
        self.within_ol = False
        self.current_dir = None
        super().__init__(*args, **kwargs)

    def handle_starttag(self, tag, attrs):
        """Restart line numbering on <ol>, capture its dir, include line number with <li>, and construct
        start tags with included attributes"""
        if tag == "ol":
            # restart line numbering, ol state indicator on encountering ol
            self.within_ol = True
            self.line_number = 1
            self.current_dir = None
            for attr, val in attrs:
                # if start present in attrs, restart to start number
                if attr == "start":
                    self.line_number = int(val)
                # capture the directionality of the list
                elif attr == "dir":
                    self.current_dir = val
        elif tag == "li" and self.within_ol:
            # append the line number as a data attribute
            attrs += [("value", str(self.line_number))]
            # propagate directionality to li if parent ol had one
            if self.current_dir and not any(a[0] == "dir" for a in attrs):
                attrs += [("dir", self.current_dir)]
            # increment line number
            self.line_number += 1
        # construct attribute definitions and final start tag string
        attr_strings = [' %s="%s"' % (attr, val) for (attr, val) in attrs]
        self.html_str += "<%s%s>" % (tag, "".join(attr_strings))

    def handle_endtag(self, tag):
        """Close all encountered HTML endtags"""
        if tag == "ol":
            self.within_ol = False
            self.current_dir = None
        self.html_str += "</%s>" % (tag,)

    def handle_data(self, data):
        """Append any text nodes as-is"""
        self.html_str += data
