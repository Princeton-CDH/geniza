import os.path

from eulxml import xmlmap

from geniza.corpus.tei_transcriptions import GenizaTei

fixture_dir = os.path.join(os.path.dirname(__file__), "fixtures")

xmlfile = os.path.join(fixture_dir, "968.xml")


def test_fields():
    tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
    assert tei.pgpid == 968
    # should have text, lines, and labels
    assert tei.text
    assert tei.lines
    assert tei.labels
    assert len(tei.labels) == 4
    assert tei.source_authors == ["Gil"]


def test_no_content():
    tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
    # this file has text content
    assert not tei.no_content()

    # if we delete the lines and labels, it does not
    tei.lines = []
    tei.labels = []
    assert tei.no_content()


def test_labels_only():
    tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
    # fixture has both labels and lines
    assert not tei.labels_only()

    # delete all the line elemens so only labels are left
    while len(tei.lines):
        del tei.lines[0]

    # now labels only is true
    assert tei.labels_only()


def test_block_format():
    tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
    blocks = tei.text_to_html(block_format=True)

    # should be a list of three items (three sets of lines separated by <label> elements)
    assert len(blocks) == 3

    # second element in list should have "Right Margin" label and 8 lines
    assert blocks[1]["label"] == "Right Margin"
    assert len(blocks[1]["lines"]) == 8

    # should use empty string for missing line number
    assert blocks[1]["lines"][5][0] == "6"
    assert blocks[1]["lines"][6][0] == ""


def test_html():
    tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
    html = tei.text_to_html()

    # should be a list with two items (two pages)
    assert len(html) == 2

    # first page should have two labels and text content
    assert html[0].count("<section>") == 2
    assert "<h1>Right Margin</h1>" in html[0]
    assert "<li>מא</li>" in html[0]
    # two different ordered lists starting with 1 (implicit start value)
    assert html[0].count("<ol>") == 2
    # both lists should be closed
    assert html[0].count("</ol>") == 2

    # second page should have one label and text content
    assert html[1].count("<section>") == 1
    assert "<h1>Recto" in html[1]
    # should have a custom starting value for list on page 2
    assert html[1].count('<ol start="11">') == 1
    assert "<li>موﻻى الشيخ ابو العﻻ</li>" in html[1]

    # check that the last line / last block is included
    assert "<li>الحسن بن ابرهيم</li>" in html[1]

    # assert that we don't get any invalid start values
    assert "start='None'" not in html[0]
    assert "start''" not in html[0]


def test_lines_to_html():
    tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
    # non number in n attribute
    html = tei.lines_to_html([("16-17", "a line")])
    assert '<ol start="16">' in html
    html = tei.lines_to_html([("A1", "another line")])
    assert "<ol>" in html
    assert "<li><b>A1</b> another line</li>" in html
    # skip empty line
    assert tei.lines_to_html([("", "  ")]) == ""


def test_text_to_plaintext():
    tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
    plaintext = tei.text_to_plaintext()
    assert plaintext.count("\n") == 43
    # two section breaks
    assert plaintext.count("\n\n") == 4
    # includes labels
    assert "Right Margin" in plaintext
    assert "מא" in plaintext
    assert "الحسن بن ابرهيم" in plaintext
    # includes line numbers and ltr/rtl marks
    assert (
        "\u200f        כתאבי אטאל אללה בקא מולי אלשיך ואדאם \u200e   1\n" in plaintext
    )


def test_text_to_plaintext_nolines():
    tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
    # delete all the lines
    tei.text.lines = []
    # should bail out when no lines are present
    assert tei.text_to_plaintext() is None


def test_text_to_plaintext_longlines():
    tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
    # replace the text of the last line with an excessively long line
    # - because the xmlobject isn't configured with an eye to updates,
    #   update the lxml node text directly
    tei.lines[-1].node.text = "superlongline" * 100
    plaintext = tei.text_to_plaintext()
    plaintext_lines = plaintext.split("\n")
    # line is slightly more than 100 because of ltr/rtl marks & line number
    # but should NOT be padded to match the superlongline
    assert len(plaintext_lines[1]) < 110


def test_label_indicates_new_page():
    tei = GenizaTei()
    assert tei.label_indicates_new_page("recto a") is True
    assert tei.label_indicates_new_page("on verso") is True
    assert tei.label_indicates_new_page("T-S ...") is True
    assert tei.label_indicates_new_page("ENA # ...") is True
    assert tei.label_indicates_new_page('ע"ב') is True
    assert tei.label_indicates_new_page("ע“ב") is True
