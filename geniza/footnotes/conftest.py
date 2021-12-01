import pytest

from geniza.footnotes.models import (
    Authorship,
    Creator,
    Footnote,
    Source,
    SourceLanguage,
    SourceType,
)


@pytest.fixture
def source(db):
    # fixture to create and return a source with one authors
    orwell = Creator.objects.create(last_name="Orwell", first_name="George")
    essay = SourceType.objects.create(type="Essay")
    english = SourceLanguage.objects.get(name="English")
    cup_of_tea = Source.objects.create(title="A Nice Cup of Tea", source_type=essay)
    cup_of_tea.languages.add(english)
    cup_of_tea.authors.add(orwell)
    return cup_of_tea


@pytest.fixture
def twoauthor_source(db):
    # fixture to create and return a source with two authors
    kernighan = Creator.objects.create(last_name="Kernighan", first_name="Brian")
    ritchie = Creator.objects.create(last_name="Ritchie", first_name="Dennis")
    book = SourceType.objects.get(type="Book")
    cprog = Source.objects.create(title="The C Programming Language", source_type=book)
    Authorship.objects.create(creator=kernighan, source=cprog)
    Authorship.objects.create(creator=ritchie, source=cprog, sort_order=2)
    return cprog


@pytest.fixture
def multiauthor_untitledsource(db):
    # fixture to create and return a source with mutiple authors, no title
    unpub = SourceType.objects.get(type="Unpublished")
    source = Source.objects.create(source_type=unpub)
    for i, name in enumerate(["Khan", "el-Leithy", "Rustow", "Vanthieghem"]):
        author = Creator.objects.create(last_name=name)
        Authorship.objects.create(creator=author, source=source, sort_order=i)
    return source


@pytest.fixture
def article(db):
    # fixture to create and return an article source
    goitein = Creator.objects.create(last_name="Goitein", first_name="S. D.")
    article = SourceType.objects.get(type="Article")
    tarbiz = Source.objects.create(
        title="Shemarya",
        journal="Tarbiz",
        source_type=article,
        volume="32",
        year=1963,
    )
    Authorship.objects.create(creator=goitein, source=tarbiz)
    return tarbiz


@pytest.fixture
def typed_texts(db):
    # fixture for unpublished source
    unpub = SourceType.objects.get(type="Unpublished")
    source = Source.objects.create(source_type=unpub, title="typed texts", volume="CUL")
    author = Creator.objects.create(last_name="Goitein", first_name="S. D.")
    Authorship.objects.create(creator=author, source=source)
    return source


@pytest.fixture
def book_section(db):
    # fixture to create and return a book section source
    section_type = SourceType.objects.get(type="Book Section")
    author = Creator.objects.create(last_name="Melammed", first_name="Renée Levine")
    book_sect = Source.objects.create(
        source_type=section_type,
        title="A Look at Women's Lives in Cairo Geniza Society",
        journal="Festschrift Darkhei Noam: The Jews of Arab Lands",
        year=2015,
        publisher="Brill",
        place_published="Leiden",
    )
    Authorship.objects.create(creator=author, source=book_sect)
    return book_sect
