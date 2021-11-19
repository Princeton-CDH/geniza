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

    def no_content(self):
        return str(self.text).strip() == ""

    def text_to_html(self):
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
                lines.append((line.number, str(line)))

        # append the last block
        if lines:
            blocks.append(
                {
                    "label": "\n".join(label),
                    "lines": lines,
                }
            )

        # combine blocks of text into html
        html = []
        for block in blocks:
            output = ["<section>"]
            # add label if we have one
            if block["label"]:
                output.append(f" <h1>{block['label']}</h1>")

            text_lines = " <ul>%s</ul>" % "".join(
                f"\n <li value='{line_number}'>{line}</li>"
                for line_number, line in block["lines"]
                if line.strip()
            )
            output.append(text_lines)
            output.append("</section>")
            html.append("\n".join(output))

        return "\n".join(html)
