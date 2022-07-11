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

    new_page_indicators = ["recto", "verso", "side ii"]

    def label_indicates_new_page(self, label):
        label = label.lower()
        return any([side_label in label for side_label in self.new_page_indicators])

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

        # combine blocks of text into html, chunked into pages to match sides of images
        html = []
        page = []
        for block in blocks:

            # if there is a label and it looks like a new side,
            # start a new section
            if block["label"]:
                # maybe "page b " could also be a new page
                if self.label_indicates_new_page(block["label"]):
                    # any([side_label in label for side_label in ["recto", "verso"]]):
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

            text_lines = " <ul>%s</ul>" % "".join(
                "\n <li%s>%s</li>"
                % (f" value='{line_number}'" if line_number else "", line)
                for line_number, line in block["lines"]
                if line.strip()
            )
            output.append(text_lines)
            output.append("</section>")
            page.append("\n".join(output))

        # save the last page
        html.append("\n".join(page))

        return html

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
