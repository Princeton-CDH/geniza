import os.path

from django.db.models.functions import text
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


def test_no_content():
    tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
    # this file has text content
    assert not tei.no_content()

    # if we delete the lines and labels, it does not
    tei.lines = []
    tei.labels = []
    assert tei.no_content()


def test_html():
    tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
    html = tei.text_to_html()
    # should result in 3 sections
    assert html.count("<section>") == 3
    assert "<h1>Right Margin</h1>" in html
    assert "<li value='1'>מא</li>" in html
    # three different lines that are # 1
    assert html.count("<li value='1'>") == 3

    # check that the last line / last block is included
    assert "<li value='6'>الحسن بن ابرهيم</li>" in html


def test_text_to_plaintext():
    tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
    plaintext = tei.text_to_plaintext()
    assert plaintext.count("\n") == 39
    # two section breaks
    assert plaintext.count("\n\n") == 2
    assert "Right Margin" not in plaintext
    assert "מא" in plaintext
    assert "الحسن بن ابرهيم" in plaintext
