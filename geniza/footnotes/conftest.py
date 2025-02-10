import pytest

from geniza.footnotes.models import (
    Authorship,
    Creator,
    Source,
    SourceLanguage,
    SourceType,
)


@pytest.fixture
def source(db):
    # fixture to create and return a source with one authors
    orwell = Creator.objects.create(last_name_en="Orwell", first_name_en="George")
    essay = SourceType.objects.create(type="Essay")
    english = SourceLanguage.objects.get(name="English")
    cup_of_tea = Source.objects.create(title_en="A Nice Cup of Tea", source_type=essay)
    cup_of_tea.languages.add(english)
    cup_of_tea.authors.add(orwell)
    return cup_of_tea


@pytest.fixture
def twoauthor_source(db):
    # fixture to create and return a source with two authors
    kernighan = Creator.objects.create(last_name_en="Kernighan", first_name_en="Brian")
    ritchie = Creator.objects.create(last_name_en="Ritchie", first_name_en="Dennis")
    book = SourceType.objects.get(type="Book")
    cprog = Source.objects.create(
        title_en="The C Programming Language", source_type=book
    )
    Authorship.objects.create(creator=kernighan, source=cprog)
    Authorship.objects.create(creator=ritchie, source=cprog, sort_order=2)
    return cprog


@pytest.fixture
def multiauthor_untitledsource(db):
    # fixture to create and return a source with mutiple authors, no title
    unpub = SourceType.objects.get(type="Unpublished")
    source = Source.objects.create(source_type=unpub)
    for i, name in enumerate(["Khan", "el-Leithy", "Rustow", "Vanthieghem"]):
        author = Creator.objects.create(last_name_en=name)
        Authorship.objects.create(creator=author, source=source, sort_order=i)
    return source


@pytest.fixture
def article(db):
    # fixture to create and return an article source
    goitein = Creator.objects.create(last_name_en="Goitein", first_name_en="S. D.")
    article = SourceType.objects.get(type="Article")
    tarbiz = Source.objects.create(
        title_en="Shemarya",
        journal="Tarbiz",
        source_type=article,
        volume="32",
        issue=1,
        year=1963,
    )
    Authorship.objects.create(creator=goitein, source=tarbiz)
    return tarbiz


@pytest.fixture
def unpublished_editions(db):
    # fixture for unpublished source
    unpub = SourceType.objects.get(type="Unpublished")
    source = Source.objects.create(
        source_type=unpub, title_en="unpublished editions", volume="CUL"
    )
    author = Creator.objects.create(last_name_en="Goitein", first_name_en="S. D.")
    Authorship.objects.create(creator=author, source=source)
    return source


@pytest.fixture
def index_cards(db):
    # fixture for unpublished index cards
    (unpub, _) = SourceType.objects.get_or_create(type="Unpublished")
    source = Source.objects.create(
        source_type=unpub, title_en="index cards", volume="CUL"
    )
    (author, _) = Creator.objects.get_or_create(
        last_name_en="Goitein", first_name_en="S. D."
    )
    Authorship.objects.create(creator=author, source=source)
    return source


@pytest.fixture
def goitein_editions(db):
    # fixture for Goitein unpublished editions
    (unpub, _) = SourceType.objects.get_or_create(type="Unpublished")
    source = Source.objects.create(
        source_type=unpub, title_en="unpublished editions", volume="CUL"
    )
    (author, _) = Creator.objects.get_or_create(
        last_name_en="Goitein", first_name_en="S. D."
    )
    Authorship.objects.create(creator=author, source=source)
    return source


@pytest.fixture
def book_section(db):
    # fixture to create and return a book section source
    section_type = SourceType.objects.get(type="Book Section")
    author = Creator.objects.create(
        last_name_en="Melammed", first_name_en="Renée Levine"
    )
    book_sect = Source.objects.create(
        source_type=section_type,
        title_en="A Look at Women's Lives in Cairo Geniza Society",
        journal="Festschrift Darkhei Noam: The Jews of Arab Lands",
        year=2015,
        publisher="Brill",
        place_published="Leiden",
        page_range="64–85",
        volume="1",
        edition=2,
    )
    Authorship.objects.create(creator=author, source=book_sect)
    return book_sect


@pytest.fixture
def phd_dissertation(db):
    # fixture to create and return a PhD dissertation source
    diss_type = SourceType.objects.get(type="Dissertation")
    author = Creator.objects.create(last_name_en="Zinger", first_name_en="Oded")
    dissertation = Source.objects.create(
        source_type=diss_type,
        title_en="Women, Gender and Law: Marital Disputes According to Documents of the Cairo Geniza",
        year=2014,
        place_published="Princeton, NJ",
        publisher="Princeton University",
    )
    Authorship.objects.create(creator=author, source=dissertation)
    return dissertation
