from eulxml import xmlmap
from eulxml.xmlmap import teimap


class GenizaTeiLine(teimap.TeiLine):
    name = xmlmap.StringField("local-name(.)")
    lang = xmlmap.StringField("@xml:lang|tei:span/@xml:lang")
    number = xmlmap.StringField("@n")


class MainText(teimap.TeiDiv):
    lines = xmlmap.NodeListField("tei:l|tei:label", GenizaTeiLine)


class GenizaTei(teimap.Tei):
    # extend eulxml TEI to add mappings for the fields we care about
    # NOTE: at least one pgpid is in format ### + ###
    pgpid = xmlmap.IntegerField('tei:teiHeader//tei:idno[@type="PGP"]')
    # normally main text content is under text/body/div; but at least one document has no div
    text = xmlmap.NodeField(
        "tei:text/tei:body/tei:div|tei:text/tei:body[not(tei:div)]", MainText
    )
    lines = xmlmap.NodeListField("tei:text/tei:body/tei:div/tei:l", GenizaTeiLine)
    labels = xmlmap.NodeListField(
        "tei:text/tei:body/tei:div/tei:label", GenizaTeiLine
    )  # not really a line...
    # source description sometimes contains reference to scholarship record
    source = xmlmap.NodeListField(
        "tei:teiHeader//tei:sourceDesc/tei:msDesc/tei:msContents/tei:p", GenizaTeiLine
    )
    # for documents with more than one transcription, authors have been
    # tagged with last name in n attribute to allow identifying/differentiating
    source_authors = xmlmap.StringListField(
        "tei:teiHeader//tei:sourceDesc//tei:author/@n"
    )

    def no_content(self):
        return str(self.text).strip() == ""

    # text that generally indicates a new page/image, anywhere in the label
    new_page_indicators = [
        "recto",
        "verso",
        "side ii",
        "page b",
        "page 2",
        "page two",
        "ע“ב",  # Hebrew label for page 2
    ]
    # text that indicates a new page/image at the start of the label
    new_page_start_indicators = ["t-s ", "ts ", "ena ", "moss. "]

    def label_indicates_new_page(self, label):
        label = label.lower()
        return any(
            [side_label in label for side_label in self.new_page_indicators]
        ) or any(
            label.startswith(start_label)
            for start_label in self.new_page_start_indicators
        )

    def labels_only(self):
        text_content = str(self.text).strip()
        label_content = " ".join([str(label).strip() for label in self.labels])
        return text_content == label_content

    def text_to_html(self, block_format=False):
        # convert the TEI text content to basic HTML
        blocks = []
        lines = []
        label = []
        # because blocks are indicated by labels without containing elements,
        # iterate over all lines and create blocks based on the labels
        for line in self.text.lines:
            if line.name == "label":
                # append current text block if set, and initialize a new one
                if lines:
                    blocks.append(
                        {
                            "label": "\n".join(label),
                            "lines": lines,
                            # "languages": list(languages),
                        }
                    )
                    label = []
                    lines = []

                # store the label; sometimes there are two in a row
                label.append(str(line))

            elif line.name == "l":
                # use language codes? unreliable in the xml
                # append tuple of line number, text
                # return empty string for line number if no line attribute
                lines.append((line.number or "", str(line)))

        # append the last block
        if lines:
            blocks.append(
                {
                    "label": "\n".join(label),
                    "lines": lines,
                }
            )

        # if block format requested, return blocks without further processing
        if block_format:
            return blocks

        # otherwise, return chunked HTML
        return self.chunk_html(blocks)

    def chunk_html(self, blocks):
        # combine blocks of text into html, chunked into pages to match sides of images
        html = []
        page = []
        for block in blocks:

            # if there is a label and it looks like a new side,
            # start a new section
            if block["label"]:
                if self.label_indicates_new_page(block["label"]):
                    # if we have any content, close the previous section
                    if page:
                        # combine all sections in the page and add to the html
                        html.append("\n".join(page))
                        # then start a new page
                        page = []

            # start output for the new block
            output = ["<section>"]
            # add label if we have one
            if block["label"]:
                output.append(f" <h1>{block['label']}</h1>")

            output.append(self.lines_to_html(block["lines"]))
            output.append("</section>")
            page.append("\n".join(output))

        # save the last page
        html.append("\n".join(page))

        return html

    def lines_to_html(self, lines):
        """Convert lines and line numbers from TEI to HTML, accounting
        for unnumbered lines and lines starting with numbers other than 1.
        Converts to ordered lists and paragraphs; ordered lists have
        start attribute when needed.

        :params lines: list of tuples of line number, line text
        :returns: string of html content
        """

        html_lines = []
        list_num = 1
        in_list = False
        for line_number, line in lines:
            # convertline number to integer for comparison
            if line_number:
                try:
                    line_number = int(line_number)
                except ValueError:
                    # in at least one instance, line number is a range "16-17"
                    # ignore the problem (??)
                    if "-" in line_number:
                        line_number = int(line_number.split("-")[0])

            # if line is empty, skip it
            if not line.strip():
                continue

            # if line is unnumberred, output as a paragraph
            if not line_number:
                # if we were in a list, close it
                if in_list:
                    html_lines.append("</ol>")
                    in_list = False
                    list_num = 1
                html_lines.append("<p>%s</p>" % line)

            # if line number is 1, start a new list
            elif line_number == 1:
                # close any preceeding list
                if in_list:
                    html_lines.append("</ol>")

                in_list = True
                list_num = 1
                html_lines.append("<ol>")
                html_lines.append("<li>%s</li>" % line)
            # if the line number matches expected next value, output as line
            elif line_number == list_num:
                html_lines.append("<li>%s</li>" % line)

            # if line number does not match expected list number,
            # start a new list with start attribute specified
            else:
                # close existing list if any
                if in_list:
                    html_lines.append("</ol>")

                # start a new list with the specified number IF numeric
                if isinstance(line_number, int):
                    list_num = line_number
                    in_list = True
                    html_lines.append('<ol start="%s">' % line_number)
                    html_lines.append("<li>%s</li>" % line)
                else:
                    # if not numeric, we can't use as line number or start
                    html_lines.append("<ol>")
                    # add to text to preserve the content
                    html_lines.append("<li><b>%s<b> %s</li>" % (line_number, line))

            # increment expected list number if we're inside a list
            if in_list:
                list_num += 1

        # close the last list, if active
        if in_list:
            html_lines.append("</ol>")

        return "\n".join(html_lines)

    rtl_mark = "\u200F"
    ltr_mark = "\u200E"

    def text_to_plaintext(self):
        lines = []
        # because blocks are indicated by labels without containing elements,
        # iterate over all lines and create blocks based on the labels

        # errors if there are no lines; sync transcription now checks
        # and won't call in that case
        if not self.text.lines:
            return

        # determine longest line so we can pad the text
        longest_line = max(len(str(line)) for line in self.text.lines)
        # some files have descriptions that are making lines much too long,
        # so set a limit on line length
        if longest_line > 100:
            longest_line = 100
        for line in self.text.lines:
            if line.name == "label":
                # blank line to indicate breaks between blocks
                lines.append("")
                lines.append("%s%s" % (self.ltr_mark, line))
            elif line.name == "l":
                line_num = line.number or ""
                # combine line text with line number and right justify;
                # right justify line number
                lines.append(
                    " ".join(
                        [
                            self.rtl_mark,
                            str(line).rjust(longest_line),
                            self.ltr_mark,
                            line_num.rjust(3),
                        ]
                    )
                )

        return "\n".join(lines)
