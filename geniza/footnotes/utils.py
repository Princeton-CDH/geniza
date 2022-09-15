from html.parser import HTMLParser


class HTMLLineNumberParser(HTMLParser):
    """HTML parser to add numbering to line elements for search indexing purposes"""

    def __init__(self, *args, **kwargs):
        """Initialize empty string and line numbering at 1"""
        self.html_str = ""
        self.line_number = 1
        self.within_ol = False
        super().__init__(*args, **kwargs)

    def handle_starttag(self, tag, attrs):
        """Restart line numbering on <ol>, include line number with <li>, and construct
        start tags with included attributes"""
        if tag == "ol":
            # restart line numbering, ol state indicator on encountering ol
            self.within_ol = True
            self.line_number = 1
            for (attr, val) in attrs:
                # if start present in attrs, restart to start number
                if attr == "start":
                    self.line_number = int(val)
        elif tag == "li" and self.within_ol:
            # append the line number as a data attribute
            attrs += [("value", str(self.line_number))]
            # increment line number
            self.line_number += 1
        # construct attribute definitions and final start tag string
        attr_strings = [' %s="%s"' % (attr, val) for (attr, val) in attrs]
        self.html_str += "<%s%s>" % (tag, "".join(attr_strings))

    def handle_endtag(self, tag):
        """Close all encountered HTML endtags"""
        if tag == "ol":
            self.within_ol = False
        self.html_str += "</%s>" % (tag,)

    def handle_data(self, data):
        """Append any text nodes as-is"""
        self.html_str += data
