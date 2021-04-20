import pytest

from taggit.models import Tag

from geniza.corpus.models import Document, DocumentType, Fragment, TextBlock

@pytest.fixture
def fragment(db):
    """A real fragment from CUL, with URLs for testing."""
    return Fragment.objects.create(
        shelfmark="CUL Add.2586",
        url="https://cudl.lib.cam.ac.uk/view/MS-ADD-02586",
        iiif_url="https://cudl.lib.cam.ac.uk/iiif/MS-ADD-02586",
    )

@pytest.fixture
def multifragment(db):
    """A real multifragment object, with fake URLs for testing."""
    return Fragment.objects.create(
        shelfmark="T-S 16.377",
        url="https://example.com/view/TS16.377",
        iiif_url="https://iiif.example.com/TS16.377",
        multifragment=True,
    )

@pytest.fixture
def document(db, fragment):
    """A real legal document from the PGP."""
    doc = Document.objects.create(
        id=3951,
        description="""Deed of sale in which a father sells to his son a quarter
         of the apartment belonging to him in a house in the al- Mu'tamid 
         passage of the Tujib quarter for seventeen dinars. Dated 1233. 
         (Information from Mediterranean Society, IV, p. 281)""",
        doctype=DocumentType.objects.get_or_create("Legal")[0],
    )
    TextBlock.objects.create(document=doc, fragment=fragment)
    doc.tags.add(Tag.objects.get_or_create(name="bill of sale")[0])
    doc.tags.add(Tag.objects.get_or_create(name="real estate")[0])
    return doc

@pytest.fixture
def join(db, fragment, multifragment):
    """A fake letter document that occurs on two different fragments."""
    doc = Document.objects.create(
        description="testing description",
        doctype=DocumentType.objects.get_or_create("Letter")[0]
    )
    TextBlock.objects.create(document=doc, fragment=fragment)
    TextBlock.objects.create(document=doc, fragment=multifragment)
    return doc