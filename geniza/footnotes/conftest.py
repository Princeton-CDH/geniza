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
    # S. D. Goitein, "New Sources from the Geniza" (Hebrew), Tarbiz 18 (1954): 7–19
    goitein = Creator.objects.create(last_name="Goitein", first_name="S. D.")
    article = SourceType.objects.get(type="Article")
    languages = SourceLanguage.objects.filter(name="Hebrew")
    tarbiz = Source.objects.create(
        title="New Sources from the Geniza",
        journal="Tarbiz",
        source_type=article,
        volume="18",
        year=1954,
        page_range="7–19",
    )
    tarbiz.languages.add(*languages)
    Authorship.objects.create(creator=goitein, source=tarbiz)
    return tarbiz


@pytest.fixture
def source_book(db):
    # fixture to create and return an book source
    # Moshe Gil, Palestine during the First Muslim Period, 634–1099, in Hebrew (Tel Aviv, 1983), vol. 2, doc. 134

    gil = Creator.objects.create(last_name="Gil", first_name="Moshe")
    book = SourceType.objects.get(type="Book")
    languages = SourceLanguage.objects.filter(name="Hebrew")
    palestine = Source.objects.create(
        title="Palestine during the First Muslim Period, 634–1099",
        source_type=book,
        volume="vol. 2",
        year=1983,
        page_range="doc. 134",
    )
    palestine.languages.add(*languages)
    Authorship.objects.create(creator=gil, source=palestine)
    return palestine


@pytest.fixture
def blog(db):
    # fixture to create and return a blog source
    goitein = Creator.objects.create(last_name="Goitein", first_name="S. D.")
    blog = SourceType.objects.get(type="Blog")
    myBlog = Source.objects.create(
        title="My Blog Post",
        source_type=blog,
    )
    Authorship.objects.create(creator=goitein, source=myBlog)
    return myBlog
