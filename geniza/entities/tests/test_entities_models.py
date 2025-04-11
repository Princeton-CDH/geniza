from datetime import datetime
from unittest.mock import patch

import pytest
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.forms import ValidationError
from django.utils import timezone
from parasolr.django.indexing import ModelIndexable
from slugify import slugify
from unidecode import unidecode

from geniza.corpus.dates import PartialDate, standard_date_display
from geniza.corpus.models import Dating, Document
from geniza.entities.models import (
    DocumentPlaceRelation,
    DocumentPlaceRelationType,
    Event,
    Name,
    PastPersonSlug,
    PastPlaceSlug,
    Person,
    PersonDocumentRelation,
    PersonDocumentRelationType,
    PersonEventRelation,
    PersonPersonRelation,
    PersonPersonRelationType,
    PersonPlaceRelation,
    PersonPlaceRelationType,
    PersonRole,
    PersonSignalHandlers,
    PersonSolrQuerySet,
    Place,
    PlaceEventRelation,
    PlacePlaceRelation,
    PlacePlaceRelationType,
    PlaceSignalHandlers,
)
from geniza.footnotes.models import Footnote


@pytest.mark.django_db
class TestNameQuerySet:
    def test_non_primary(self):
        person = Person.objects.create()
        name = Name.objects.create(
            name="S.D. Goitein", content_object=person, primary=True
        )
        non_primary = Name.objects.create(
            name="Goitein", content_object=person, primary=False
        )
        # should filter out primary names, only include non-primary
        assert person.names.non_primary().exists()
        assert person.names.non_primary().count() == 1
        assert name not in person.names.non_primary()
        assert non_primary in person.names.non_primary()


@pytest.mark.django_db
class TestName:
    def test_save_unicode_cleanup(self):
        # Should cleanup \xa0 from name
        person = Person.objects.create()
        name = Name.objects.create(
            name="Shelomo\xa0 Dov Goitein", content_object=person
        )
        assert name.name == "Shelomo Dov Goitein"


@pytest.mark.django_db
class TestPerson:
    def test_str(self):
        person = Person.objects.create()
        # Person with no name uses default django __str__ method
        assert str(person) == f"Person object ({person.pk})"
        # add two names
        secondary_name = Name.objects.create(
            name="Shelomo Dov Goitein", content_object=person
        )
        primary_name = Name.objects.create(name="S.D. Goitein", content_object=person)
        # __str__ should use the first name added
        assert str(person) == secondary_name.name
        # set one of them as primary
        primary_name.primary = True
        primary_name.save()
        # __str__ should use the primary name
        assert str(person) == primary_name.name

    def test_merge_with(self):
        # create two people
        person = Person.objects.create(
            description_en="a person",
            gender=Person.UNKNOWN,
        )
        role = PersonRole.objects.create(name="example")
        person_2 = Person.objects.create(
            description_en="testing description",
            gender=Person.FEMALE,
            role=role,
            has_page=True,
        )
        p2_str = str(person_2)
        person.merge_with([person_2])
        # migrated public page override/missing info
        assert person.role == role
        assert person.gender == Person.FEMALE
        assert person.has_page == True
        # combined descriptions
        assert "a person" in person.description
        assert "\nDescription from merged entry:" in person.description
        assert "testing description" in person.description
        # should delete and create merge log entry
        assert not person_2.pk
        assert LogEntry.objects.filter(
            object_id=person.pk, change_message__contains=f"merged with {p2_str}"
        ).exists()

    def test_merge_with_no_description(self):
        # create two people
        person = Person.objects.create(
            gender=Person.UNKNOWN,
        )
        role = PersonRole.objects.create(name="example")
        person_2 = Person.objects.create(
            description_en="testing description",
            gender=Person.FEMALE,
            role=role,
            has_page=True,
        )
        person.merge_with([person_2])
        # should not error; should combine descriptions
        assert "Description from merged entry:" in person.description
        assert "testing description" in person.description

    def test_merge_with_conflicts(self):
        # should raise ValidationError on conflicting gender
        person = Person.objects.create(gender=Person.MALE)
        person_2 = Person.objects.create(gender=Person.FEMALE)
        with pytest.raises(ValidationError):
            person.merge_with([person_2])
        # should raise ValidationError on conflicting role
        role = PersonRole.objects.create(name="example")
        role_2 = PersonRole.objects.create(name="other")
        person_3 = Person.objects.create(gender=Person.MALE, role=role)
        person_4 = Person.objects.create(gender=Person.MALE, role=role_2)
        with pytest.raises(ValidationError):
            person_3.merge_with([person_4])

    def test_merge_with_names(self):
        person = Person.objects.create()
        Name.objects.create(name="S.D. Goitein", content_object=person, primary=True)
        Name.objects.create(name="Shelomo Dov Goitein", content_object=person)
        person_dupe = Person.objects.create()
        dupe_name = Name.objects.create(name="S.D. Goitein", content_object=person_dupe)
        primary_name = Name.objects.create(
            name="S.D.G.", content_object=person_dupe, primary=True
        )
        person.merge_with([person_dupe])
        # identical name should not get added
        assert not person.names.filter(pk=dupe_name.pk).exists()
        # dupe's primary name should be added since it's unique, but should not be primary anymore
        assert person.names.filter(pk=primary_name.pk, primary=False).exists()

    def test_merge_with_related_people(self):
        parent = Person.objects.create()
        parent_dupe = Person.objects.create()
        child = Person.objects.create()
        grandchild = Person.objects.create()
        # "possible same" relation between person and dupe
        ambiguity_type, _ = PersonPersonRelationType.objects.get_or_create(
            name_en="possibly the same as"
        )
        PersonPersonRelation.objects.create(
            from_person=parent, to_person=parent_dupe, type=ambiguity_type
        )
        # parent relation between dupe and child
        parent_type, _ = PersonPersonRelationType.objects.get_or_create(
            name_en="parent", converse_name_en="child"
        )
        PersonPersonRelation.objects.create(
            from_person=parent_dupe, to_person=child, type=parent_type
        )
        # grandchild relation between grandchild and dupe
        grandchild_type, _ = PersonPersonRelationType.objects.get_or_create(
            name_en="grandchild", converse_name_en="grandparent"
        )
        PersonPersonRelation.objects.create(
            from_person=grandchild, to_person=parent_dupe, type=grandchild_type
        )
        parent.merge_with([parent_dupe])

        # ambiguity relationship should no longer be present
        assert not parent.to_person.filter(type=ambiguity_type).exists()
        assert not parent.from_person.filter(type=ambiguity_type).exists()

        # child relation should be reassigned with parent as parent
        assert PersonPersonRelation.objects.filter(
            from_person=parent, to_person=child, type=parent_type
        ).exists()

        # grandchild relation should be reassigned with parent as grandparent
        assert PersonPersonRelation.objects.filter(
            from_person=grandchild, to_person=parent, type=grandchild_type
        ).exists()

    def test_merge_with_related_places(self):
        person = Person.objects.create()
        person_dupe = Person.objects.create()
        fustat = Place.objects.create()
        origin = Place.objects.create()
        home_base, _ = PersonPlaceRelationType.objects.get_or_create(
            name_en="Home base"
        )
        family_roots, _ = PersonPlaceRelationType.objects.get_or_create(
            name_en="Family traces roots to"
        )
        # both have the same home base (same place and type)
        PersonPlaceRelation.objects.create(person=person, place=fustat, type=home_base)
        PersonPlaceRelation.objects.create(
            person=person_dupe, place=fustat, type=home_base
        )
        # dupe has family origin
        PersonPlaceRelation.objects.create(
            person=person_dupe, place=origin, type=family_roots
        )
        person.merge_with([person_dupe])
        # merged should have two relations, not three (dupe skipped)
        assert person.personplacerelation_set.count() == 2
        # merged should get family origin from dupe
        assert person.personplacerelation_set.filter(
            place=origin, type=family_roots
        ).exists()

    def test_merge_with_related_documents(self, document):
        person = Person.objects.create()
        person_dupe = Person.objects.create()
        person_dupe.documents.add(document)
        person.merge_with([person_dupe])
        # document relation should be reassigned to merged result
        assert person.documents.filter(pk=document.pk).exists()

    def test_merge_with_footnotes(self, source, twoauthor_source):
        person = Person.objects.create()
        person_dupe = Person.objects.create()
        Footnote.objects.create(
            source=source, doc_relation=Footnote.EDITION, content_object=person_dupe
        )
        Footnote.objects.create(source=twoauthor_source, content_object=person)
        Footnote.objects.create(source=twoauthor_source, content_object=person_dupe)
        person.merge_with([person_dupe])
        # should have two footnotes, not three (dupe skipped)
        assert person.footnotes.count() == 2
        # first footnote should have been migrated, but had its doc relation removed
        assert person.footnotes.filter(source=source).exists()
        assert not person.footnotes.filter(doc_relation=Footnote.EDITION).exists()

    def test_merge_with_log_entries(self):
        # heavily adapted from document merge test
        person = Person.objects.create()
        Name.objects.create(name="S.D. Goitein", content_object=person, primary=True)
        person_dupe = Person.objects.create()
        Name.objects.create(
            name="Shelomo Dov Goitein", content_object=person_dupe, primary=True
        )

        # create some log entries
        person_contenttype = ContentType.objects.get_for_model(Person)
        # creation
        creation_date = timezone.make_aware(datetime(2023, 10, 12))
        creator = User.objects.get_or_create(username="editor")[0]
        LogEntry.objects.bulk_create(
            [
                LogEntry(
                    user_id=creator.id,
                    content_type_id=person_contenttype.pk,
                    object_id=person.id,
                    object_repr=str(person),
                    change_message="first input",
                    action_flag=ADDITION,
                    action_time=creation_date,
                ),
                LogEntry(
                    user_id=creator.id,
                    content_type_id=person_contenttype.pk,
                    object_id=person_dupe.id,
                    object_repr=str(person_dupe),
                    change_message="first input",
                    action_flag=ADDITION,
                    action_time=creation_date,
                ),
                LogEntry(
                    user_id=creator.id,
                    content_type_id=person_contenttype.pk,
                    object_id=person_dupe.id,
                    object_repr=str(person_dupe),
                    change_message="major revision",
                    action_flag=CHANGE,
                    action_time=timezone.now(),
                ),
            ]
        )

        assert person.log_entries.count() == 1
        assert person_dupe.log_entries.count() == 2
        dupe_pk = person_dupe.pk
        dupe_str = str(person_dupe)
        person.merge_with([person_dupe], user=creator)
        # should have 3 log entries after the merge:
        # 1 of the two duplicates, 1 unique from dupe,
        # and 1 documenting the merge
        assert person.log_entries.count() == 3
        # based on default sorting, most recent log entry will be first
        # - should document the merge event
        merge_log = person.log_entries.first()
        # log action with specified user
        assert creator.id == merge_log.user_id
        assert merge_log.action_flag == CHANGE

        # reassociated log entry should include dupe's primary name, id
        moved_log = person.log_entries.all()[1]
        assert (
            " [merged person %s (id = %s)]" % (dupe_str, dupe_pk)
            in moved_log.change_message
        )

    def test_get_absolute_url(self):
        # should not have an absolute url if has_page is false and < MIN_DOCUMENTS associated docs
        person = Person.objects.create()
        assert person.get_absolute_url() == None

        # has_page is true, should get the url in user's language by slug
        person.has_page = True
        assert person.get_absolute_url() == "/en/people/%s/" % person.slug

        # has_page is false but has >= MIN_DOCUMENTS, should get url
        person.has_page = False
        for _ in range(Person.MIN_DOCUMENTS):
            d = Document.objects.create()
            person.documents.add(d)
        assert person.get_absolute_url() == "/en/people/%s/" % person.slug

    def test_save(self):
        # test past slugs are recorded on save
        person = Person(slug="test")
        person.save()
        person.slug = ""
        person.save()
        assert PastPersonSlug.objects.filter(slug="test", person=person).exists()

    def test_generate_slug(self):
        person = Person.objects.create()
        Name.objects.create(name="S.D. Goitein", content_object=person, primary=True)
        person.generate_slug()

        # should use slugified, unidecoded string
        assert person.slug == slugify(unidecode(str(person)))
        person.save()

        # numeric differentiation when needed
        person2 = Person.objects.create()
        Name.objects.create(name="S.D. Goitein", content_object=person2, primary=True)
        person2.generate_slug()

        # should determine -2 based on the existence of identical slug
        assert person2.slug == f"{person.slug}-2"
        person2.save()

        # should increment if there are existing numbers
        person3 = Person.objects.create()
        Name.objects.create(name="S.D. Goitein", content_object=person3, primary=True)
        person3.generate_slug()
        assert person3.slug == f"{person.slug}-3"

        # should remove ayin and hamza
        makhluf = Person.objects.create()
        Name.objects.create(
            name="Makhlūf Neʾeman ha-Yeshiva", content_object=makhluf, primary=True
        )
        makhluf.generate_slug()
        assert "ne-eman" not in makhluf.slug
        assert "neeman" in makhluf.slug
        yeshua = Person.objects.create()
        Name.objects.create(
            name="Yeshuʿa b. Ismāʿīl al-Makhmūrī", content_object=yeshua, primary=True
        )
        yeshua.generate_slug()
        assert "yeshu-a" not in yeshua.slug
        assert "yeshua" in yeshua.slug

        # should remove ' single quotation mark
        gaon = Person.objects.create()
        Name.objects.create(name="Yoshiyyahu Ga'on", content_object=gaon, primary=True)
        gaon.generate_slug()
        assert "ga-on" not in gaon.slug
        assert "gaon" in gaon.slug

    def test_content_authors(self, person):
        # with no log entries, should have no content_authors
        assert not person.content_authors

        # create some log entries
        person_contenttype = ContentType.objects.get_for_model(Person)
        opts = {
            "object_id": str(person.pk),
            "content_type": person_contenttype,
            "object_repr": str(person),
        }
        mr = User.objects.create(username="mr", first_name="Marina", last_name="Rustow")
        LogEntry.objects.create(**opts, user=mr, action_flag=ADDITION)
        assert person.content_authors == "Marina Rustow"

        # add more authors
        tj = User.objects.create(username="tj", first_name="Tom", last_name="Jones")
        LogEntry.objects.create(**opts, user=tj, action_flag=CHANGE)
        LogEntry.objects.create(**opts, user=tj, action_flag=CHANGE)

        # should order the names alphabetically by last name, join with "and"
        assert person.content_authors == "Tom Jones and Marina Rustow"

        # should comma separate, including serial comma, when more than 2 names
        zz = User.objects.create(username="zz", first_name="Zed", last_name="Zilch")
        LogEntry.objects.create(**opts, user=zz, action_flag=CHANGE)
        assert person.content_authors == "Tom Jones, Marina Rustow, and Zed Zilch"

    def test_formatted_citation(self, person):
        person.has_page = True
        person.save()

        citation = person.formatted_citation
        # should start with person name in quotes if no content authors
        assert not person.content_authors
        assert citation.startswith(f'"{str(person)},"')

        # should include today's date
        today = datetime.today().strftime("%B %-d, %Y")
        assert today in citation

        # should include content authors if any exist
        person_contenttype = ContentType.objects.get_for_model(Person)
        mr = User.objects.create(username="mr", first_name="Marina", last_name="Rustow")
        LogEntry.objects.create(
            object_id=str(person.pk),
            content_type=person_contenttype,
            object_repr=str(person),
            user=mr,
            action_flag=ADDITION,
        )
        citation = person.formatted_citation
        assert person.content_authors in citation

    def test_date_str(self, person, document):
        # no date: empty string
        assert not person.date_str
        # document dates: should use those
        document.doc_date_standard = "1200/1300"
        document.save()
        PersonDocumentRelation.objects.create(person=person, document=document)
        assert person.date_str == standard_date_display(document.doc_date_standard)
        # person date override
        person.date = "1255"
        person.save()
        assert person.date_str == standard_date_display("1255")

    def test_solr_date_range(self, person, document, join):
        # no date: returns None
        assert not person.solr_date_range()
        # document dates: should use those
        document.doc_date_standard = "1200/1300"
        document.save()
        PersonDocumentRelation.objects.create(person=person, document=document)
        assert person.solr_date_range() == "[1200 TO 1300]"

        # should NOT include mentioned (deceased)
        (deceased, _) = PersonDocumentRelationType.objects.get_or_create(
            name="Mentioned (deceased)"
        )
        join.doc_date_standard = "1310/1312"
        join.save()
        PersonDocumentRelation.objects.create(
            person=person, document=join, type=deceased
        )
        assert person.solr_date_range() == "[1200 TO 1300]"

        # person date override
        person.date = "1255"
        person.save()
        assert person.solr_date_range() == "1255"

    def test_total_to_index(self, person, person_multiname):
        assert Person.total_to_index() == 2

    def test_index_data(self, person, person_multiname, document, join):
        document.doc_date_standard = "1200/1300"
        document.save()
        (pdrtype, _) = PersonDocumentRelationType.objects.get_or_create(name="test")
        PersonDocumentRelation.objects.create(
            person=person, document=document, type=pdrtype
        )
        (scribe, _) = PersonDocumentRelationType.objects.get_or_create(name="scribe")
        PersonDocumentRelation.objects.create(
            person=person, document=document, type=scribe, uncertain=True
        )

        # these dates should be ignored (deceased)
        (deceased, _) = PersonDocumentRelationType.objects.get_or_create(
            name="Mentioned (deceased)"
        )
        join.doc_date_standard = "1310/1312"
        join.save()
        PersonDocumentRelation.objects.create(
            person=person, document=join, type=deceased
        )

        tags = ["testtag", "tag2"]
        for t in tags:
            person.tags.add(t)
        index_data = person.index_data()
        assert index_data["slug_s"] == person.slug
        assert index_data["name_s"] == str(person)
        assert index_data["description_txt"] == person.description_en
        assert index_data["gender_s"] == person.get_gender_display()
        assert index_data["role_s"] == str(person.role)
        assert not index_data["url_s"]
        assert index_data["has_page_b"] == False
        person.has_page = True
        person.save()
        index_data = person.index_data()
        assert index_data["url_s"] == person.get_absolute_url()
        assert index_data["has_page_b"] == True
        assert index_data["documents_i"] == 2
        assert index_data["people_i"] == index_data["places_i"] == 0
        assert str(pdrtype) in index_data["document_relation_ss"]
        assert str(deceased) in index_data["document_relation_ss"]
        assert str(scribe) in index_data["document_relation_ss"]
        assert str(pdrtype) in index_data["certain_document_relation_ss"]
        assert str(deceased) in index_data["certain_document_relation_ss"]
        assert str(scribe) not in index_data["certain_document_relation_ss"]
        assert index_data["tags_ss_lower"] == tags
        assert index_data["date_dr"] == person.solr_date_range()
        assert index_data["date_str_s"] == person.date_str
        assert index_data["start_dating_i"] == PartialDate("1200").numeric_format()
        assert index_data["end_dating_i"] == PartialDate("1300").numeric_format(
            mode="max"
        )
        index_data = person_multiname.index_data()
        assert str(person_multiname) not in index_data["other_names_ss"]
        assert (
            str(person_multiname.names.non_primary().first())
            in index_data["other_names_ss"]
        )

    def test_active_date_range(self, person, document, join):
        # these dates should be used (active)
        document.doc_date_standard = "1200/1300"
        document.save()
        (pdrtype, _) = PersonDocumentRelationType.objects.get_or_create(name="test")
        PersonDocumentRelation.objects.create(
            person=person, document=document, type=pdrtype
        )
        # these dates should be ignored (deceased)
        (deceased, _) = PersonDocumentRelationType.objects.get_or_create(
            name="Mentioned (deceased)"
        )
        join.doc_date_standard = "1310/1312"
        join.save()
        PersonDocumentRelation.objects.create(
            person=person, document=join, type=deceased
        )
        assert person.active_date_range == document.doc_date_standard

    def test_deceased_date_range(self, person, document, join):
        # these dates should be ignored (active)
        document.doc_date_standard = "1200/1300"
        document.save()
        (pdrtype, _) = PersonDocumentRelationType.objects.get_or_create(name="test")
        PersonDocumentRelation.objects.create(
            person=person, document=document, type=pdrtype
        )
        # these dates should be used (deceased)
        (deceased, _) = PersonDocumentRelationType.objects.get_or_create(
            name="Mentioned (deceased)"
        )
        join.doc_date_standard = "1310/1312"
        join.save()
        PersonDocumentRelation.objects.create(
            person=person, document=join, type=deceased
        )
        assert person.deceased_date_range == join.doc_date_standard


class TestPersonSolrQuerySet:
    def test_keyword_search(self):
        pqs = PersonSolrQuerySet()
        with patch.object(pqs, "search") as mocksearch:
            pqs.keyword_search("halfon")
            mocksearch.assert_called_with(pqs.keyword_search_qf)
            mocksearch.return_value.raw_query_parameters.assert_called_with(
                **{
                    "keyword_query": "halfon",
                    "q.op": "AND",
                }
            )
            pqs.keyword_search("tag:community")
            mocksearch.return_value.raw_query_parameters.assert_called_with(
                **{
                    "keyword_query": "tags_ss_lower:community",
                    "q.op": "AND",
                }
            )

    def test_get_highlighting(self):
        pqs = PersonSolrQuerySet()
        with patch("geniza.entities.models.super") as mock_super:
            # no highlighting
            mock_get_highlighting = mock_super.return_value.get_highlighting
            mock_get_highlighting.return_value = {}
            assert pqs.get_highlighting() == {}

            # highlighting but no other_names field
            test_highlight = {"person.1": {"description": ["foo bar baz"]}}
            mock_get_highlighting.return_value = test_highlight
            # returned unchanged
            assert pqs.get_highlighting() == test_highlight

            # highlighting single other_names field
            test_highlight = {
                "person.1": {"other_names_bigram": ["<em>Yaʿaqov</em> b. Shemuʾel"]}
            }
            mock_get_highlighting.return_value = test_highlight
            # should strip html tags
            assert pqs.get_highlighting()["person.1"]["other_names"] == [
                "Yaʿaqov b. Shemuʾel"
            ]

            # highlighting multiple other_names fields
            test_highlight = {
                "person.1": {
                    "other_names_nostem": ["", "<em>Ibn</em> al-Qaṭāʾif"],
                    "other_names_bigram": ["", "<em>Ibn</em> al-Qaṭāʾif"],
                }
            }
            mock_get_highlighting.return_value = test_highlight
            # should strip html tags, dedupe, and remove empty strings
            assert pqs.get_highlighting()["person.1"]["other_names"] == [
                "Ibn al-Qaṭāʾif"
            ]


@pytest.mark.django_db
class TestPersonSignalHandlers:
    @patch.object(ModelIndexable, "index_items")
    def test_related_save(self, mock_indexitems, person, person_multiname, document):
        # unsaved name should be ignored
        name = Name(name="test name")
        PersonSignalHandlers.related_save(Name, name)
        mock_indexitems.assert_not_called()
        # raw - ignore
        PersonSignalHandlers.related_save(Name, name, raw=True)
        mock_indexitems.assert_not_called()
        # name associated with a person
        name.content_object = person
        name.save()
        PersonSignalHandlers.related_save(Name, name)
        assert mock_indexitems.call_count == 1
        assert person in mock_indexitems.call_args[0][0]

        # role
        role = person.role
        role.name_en = "changed"
        role.save()
        mock_indexitems.reset_mock()
        PersonSignalHandlers.related_save(PersonRole, role)
        assert mock_indexitems.call_count == 1
        assert person in mock_indexitems.call_args[0][0]

        # person person relation
        (ppr_type, _) = PersonPersonRelationType.objects.get_or_create(name="test")
        person_rel = PersonPersonRelation(
            from_person=person, to_person=person_multiname, type=ppr_type
        )
        person_rel.save()
        mock_indexitems.reset_mock()
        PersonSignalHandlers.related_save(PersonPersonRelation, person_rel)
        assert mock_indexitems.call_count == 1
        assert person in mock_indexitems.call_args[0][0]

        # person place relation
        rel_place = Place.objects.create()
        ppr = PersonPlaceRelation(person=person, place=rel_place)
        ppr.save()
        mock_indexitems.reset_mock()
        PersonSignalHandlers.related_save(PersonPlaceRelation, ppr)
        assert mock_indexitems.call_count == 1
        assert person in mock_indexitems.call_args[0][0]

        # person document relation
        pdr = PersonDocumentRelation(document=document, person=person)
        pdr.save()
        mock_indexitems.reset_mock()
        PersonSignalHandlers.related_save(PersonDocumentRelation, pdr)
        assert mock_indexitems.call_count == 1
        assert person in mock_indexitems.call_args[0][0]

        # unhandled model should be ignored, no error
        mock_indexitems.reset_mock()
        PersonSignalHandlers.related_save(Person, person)
        mock_indexitems.assert_not_called()

    @pytest.mark.django_db
    @patch.object(ModelIndexable, "index_items")
    def test_related_delete(self, mock_indexitems, person, document):
        # delegates to same method as save, just check a few cases

        # Name associated with a person
        name = Name(name="test name", content_object=person)
        name.save()
        # delete
        mock_indexitems.reset_mock()
        PersonSignalHandlers.related_delete(Name, name)
        assert mock_indexitems.call_count == 1
        assert person in mock_indexitems.call_args[0][0]

        # person document relation
        pdr = PersonDocumentRelation(document=document, person=person)
        pdr.save()
        mock_indexitems.reset_mock()
        PersonSignalHandlers.related_delete(PersonDocumentRelation, pdr)
        assert mock_indexitems.call_count == 1
        assert person in mock_indexitems.call_args[0][0]


@pytest.mark.django_db
class TestPersonRole:
    def test_objects_by_label(self):
        """Should return dict of PersonRole objects keyed on English label"""
        # invalidate cached property (it is computed in other tests in the suite)
        if "objects_by_label" in PersonRole.__dict__:
            # __dict__["objects_by_label"] returns a classmethod
            # __func__ returns a property
            # fget returns the actual cached function
            PersonRole.__dict__["objects_by_label"].__func__.fget.cache_clear()
        # add some new roles
        role = PersonRole(name_en="Some kind of official")
        role.save()
        role_2 = PersonRole(display_label_en="Example")
        role_2.save()
        # should be able to get a role by label
        assert isinstance(
            PersonRole.objects_by_label.get("Some kind of official"), PersonRole
        )
        # should match by name_en or display_label_en, depending on what's set
        assert PersonRole.objects_by_label.get("Some kind of official").pk == role.pk
        assert PersonRole.objects_by_label.get("Example").pk == role_2.pk

    def test_str(self):
        # str should use display label, with name as a fallback
        pr = PersonRole.objects.create(name="test")
        assert str(pr) == pr.name
        pr.display_label = "Test Display"
        assert str(pr) == pr.display_label


@pytest.mark.django_db
class TestPersonPersonRelation:
    def test_str(self):
        goitein = Person.objects.create()
        Name.objects.create(name="S.D. Goitein", content_object=goitein)
        rustow = Person.objects.create()
        Name.objects.create(name="Marina Rustow", content_object=rustow)
        friendship_type = PersonPersonRelationType.objects.create(
            name="Friend", category=PersonPersonRelationType.BUSINESS
        )
        friendship = PersonPersonRelation.objects.create(
            from_person=goitein,
            to_person=rustow,
            type=friendship_type,
        )
        assert str(friendship) == f"{friendship_type} relation: {rustow} and {goitein}"

        # with converse_name
        ayala = Person.objects.create()
        Name.objects.create(name="Ayala Gordon", content_object=ayala)
        (parent_child, _) = PersonPersonRelationType.objects.get_or_create(
            name="Parent",
            converse_name="Child",
            category=PersonPersonRelationType.IMMEDIATE_FAMILY,
        )
        goitein_ayala = PersonPersonRelation.objects.create(
            from_person=ayala,
            to_person=goitein,
            type=parent_child,
        )
        assert str(goitein_ayala) == f"Parent-Child relation: {goitein} and {ayala}"


@pytest.mark.django_db
class TestPersonDocumentRelation:
    def test_str(self):
        goitein = Person.objects.create()
        Name.objects.create(name="S.D. Goitein", content_object=goitein)
        recipient = PersonDocumentRelationType.objects.create(name="Test Recipient")
        doc = Document.objects.create()
        relation = PersonDocumentRelation.objects.create(
            person=goitein,
            document=doc,
            type=recipient,
        )
        assert str(relation) == f"{recipient} relation: {goitein} and {doc}"


@pytest.mark.django_db
class TestPersonDocumentRelationType:
    def test_merge_with(self, person, person_multiname, document, join):
        # create three PersonDocumentRelationTypes and some associations
        rel_type = PersonDocumentRelationType.objects.create(name="test")
        type_2 = PersonDocumentRelationType.objects.create(name="to be merged")
        type_3 = PersonDocumentRelationType.objects.create(name="also merge me")
        PersonDocumentRelation.objects.create(
            type=rel_type, person=person, document=document
        )
        PersonDocumentRelation.objects.create(
            type=type_2, person=person, document=document
        )
        PersonDocumentRelation.objects.create(
            type=type_2, person=person_multiname, document=document
        )
        PersonDocumentRelation.objects.create(type=type_3, person=person, document=join)

        # create some log entries
        pdrtype_contenttype = ContentType.objects.get_for_model(
            PersonDocumentRelationType
        )
        creation_date = timezone.make_aware(datetime(2023, 10, 12))
        creator = User.objects.get_or_create(username="editor")[0]
        type_2_str = str(type_2)
        type_2_pk = type_2.pk
        LogEntry.objects.bulk_create(
            [
                LogEntry(
                    user_id=creator.id,
                    content_type_id=pdrtype_contenttype.pk,
                    object_id=type_2_pk,
                    object_repr=type_2_str,
                    change_message="first input",
                    action_flag=ADDITION,
                    action_time=creation_date,
                ),
                LogEntry(
                    user_id=creator.id,
                    content_type_id=pdrtype_contenttype.pk,
                    object_id=type_2_pk,
                    object_repr=type_2_str,
                    change_message="major revision",
                    action_flag=CHANGE,
                    action_time=timezone.now(),
                ),
            ]
        )
        assert rel_type.persondocumentrelation_set.count() == 1
        rel_type.merge_with([type_2, type_3])
        # should skip the duplicate and add the others
        assert rel_type.persondocumentrelation_set.count() == 3
        # should delete other types and create merge log entry
        assert not type_2.pk
        assert not type_3.pk
        assert LogEntry.objects.filter(
            object_id=rel_type.pk,
            change_message__contains=f"merged with {type_2}, {type_3}",
        ).exists()
        assert rel_type.log_entries.count() == 3
        # based on default sorting, most recent log entry will be first
        # - should document the merge event
        merge_log = rel_type.log_entries.first()
        assert merge_log.action_flag == CHANGE

        # reassociated log entries should include merged type's name, id
        assert (
            " [merged type %s (id = %s)]" % (type_2_str, type_2_pk)
            in rel_type.log_entries.all()[1].change_message
        )
        assert (
            " [merged type %s (id = %s)]" % (type_2_str, type_2_pk)
            in rel_type.log_entries.all()[2].change_message
        )

    @pytest.mark.django_db
    def test_objects_by_label(self):
        """Should return dict of PersonDocumentRelationType objects keyed on English label"""
        # invalidate cached property (it is computed in other tests in the suite)
        if "objects_by_label" in PersonDocumentRelationType.__dict__:
            # __dict__["objects_by_label"] returns a classmethod
            # __func__ returns a property
            # fget returns the actual cached function
            PersonDocumentRelationType.__dict__[
                "objects_by_label"
            ].__func__.fget.cache_clear()
        # add some new relation types
        rel_type = PersonDocumentRelationType(name="Some kind of official")
        rel_type.save()
        rel_type_2 = PersonDocumentRelationType(name="Example")
        rel_type_2.save()
        # should be able to get a relation type by label
        assert isinstance(
            PersonDocumentRelationType.objects_by_label.get("Some kind of official"),
            PersonDocumentRelationType,
        )
        assert (
            PersonDocumentRelationType.objects_by_label.get("Some kind of official").pk
            == rel_type.pk
        )
        assert (
            PersonDocumentRelationType.objects_by_label.get("Example").pk
            == rel_type_2.pk
        )


@pytest.mark.django_db
class TestPersonPersonRelationType:
    def test_merge_with(self, person, person_multiname, person_diacritic):
        # create two PersonPersonRelationTypes and some associations
        rel_type = PersonPersonRelationType.objects.create(name="test")
        type_2 = PersonPersonRelationType.objects.create(name="to be merged")
        PersonPersonRelation.objects.create(
            type=rel_type, from_person=person, to_person=person_multiname
        )
        PersonPersonRelation.objects.create(
            type=type_2, from_person=person, to_person=person_diacritic
        )

        # create some log entries
        pprtype_contenttype = ContentType.objects.get_for_model(
            PersonPersonRelationType
        )
        creation_date = timezone.make_aware(datetime(2025, 1, 22))
        creator = User.objects.get_or_create(username="editor")[0]
        type_2_str = str(type_2)
        type_2_pk = type_2.pk
        LogEntry.objects.bulk_create(
            [
                LogEntry(
                    user_id=creator.id,
                    content_type_id=pprtype_contenttype.pk,
                    object_id=type_2_pk,
                    object_repr=type_2_str,
                    change_message="first input",
                    action_flag=ADDITION,
                    action_time=creation_date,
                ),
                LogEntry(
                    user_id=creator.id,
                    content_type_id=pprtype_contenttype.pk,
                    object_id=type_2_pk,
                    object_repr=type_2_str,
                    change_message="major revision",
                    action_flag=CHANGE,
                    action_time=timezone.now(),
                ),
            ]
        )
        assert rel_type.personpersonrelation_set.count() == 1
        rel_type.merge_with([type_2])
        assert rel_type.personpersonrelation_set.count() == 2
        # should delete other types and create merge log entry
        assert not type_2.pk
        assert LogEntry.objects.filter(
            object_id=rel_type.pk,
            change_message__contains=f"merged with {type_2}",
        ).exists()
        assert rel_type.log_entries.count() == 3
        # based on default sorting, most recent log entry will be first
        # - should document the merge event
        merge_log = rel_type.log_entries.first()
        assert merge_log.action_flag == CHANGE

        # reassociated log entries should include merged type's name, id
        assert (
            " [merged type %s (id = %s)]" % (type_2_str, type_2_pk)
            in rel_type.log_entries.all()[1].change_message
        )
        assert (
            " [merged type %s (id = %s)]" % (type_2_str, type_2_pk)
            in rel_type.log_entries.all()[2].change_message
        )


@pytest.mark.django_db
class TestPlace:
    def test_str(self):
        place = Place.objects.create()
        # Place with no name uses default django __str__ method
        assert str(place) == f"Place object ({place.pk})"
        # add two names
        secondary_name = Name.objects.create(name="Philly", content_object=place)
        primary_name = Name.objects.create(name="Philadelphia", content_object=place)
        # __str__ should use the first name added
        assert str(place) == secondary_name.name
        # set one of them as primary
        primary_name.primary = True
        primary_name.save()
        # __str__ should use the primary name
        assert str(place) == primary_name.name

    def test_save(self):
        # test past slugs are recorded on save
        place = Place(slug="test")
        place.save()
        place.slug = ""
        place.save()
        assert PastPlaceSlug.objects.filter(slug="test", place=place).exists()

    def test_get_absolute_url(self):
        # should get place page url in user's language by slug
        place = Place.objects.create()
        Name.objects.create(name="place", content_object=place)
        place.generate_slug()
        place.save()
        assert place.get_absolute_url() == "/en/places/%s/" % place.slug

    def test_coordinates(self):
        # should convert coordinates from decimal to DMS, and output
        # as a human-readable string
        fustat = Place.objects.create(latitude=30.0050, longitude=31.2375)
        assert fustat.coordinates == "30° 0′ 17″ N, 31° 14′ 15″ E"

        # a place without coordinates should return an empty strng
        noplace = Place.objects.create()
        assert not noplace.coordinates

    def test_total_to_index(self):
        assert Place.total_to_index() == 0
        [Place.objects.create() for _ in range(3)]
        assert Place.total_to_index() == 3

    def test_items_to_index(self):
        place = Place.objects.create()
        Name.objects.create(content_object=place, name="test")
        places = Place.items_to_index()
        assert place in places

    def test_index_data(self, document, join):
        mosul = Place.objects.create(latitude=36.34, longitude=43.13)
        pname = Name.objects.create(content_object=mosul, name="Mosul", primary=True)
        oname = Name.objects.create(content_object=mosul, name="الموصل", primary=False)
        mosul.generate_slug()
        DocumentPlaceRelation.objects.create(place=mosul, document=document)
        DocumentPlaceRelation.objects.create(place=mosul, document=join)
        person = Person.objects.create()
        PersonPlaceRelation.objects.create(person=person, place=mosul)
        index_data = mosul.index_data()

        assert index_data["slug_s"] == mosul.slug
        assert index_data["name_s"] == pname.name
        assert index_data["other_names_s"] == oname.name
        assert index_data["url_s"] == mosul.get_absolute_url()
        assert index_data["location_p"] == "36.34,43.13"
        assert index_data["documents_i"] == 2
        assert index_data["people_i"] == 1


@pytest.mark.django_db
class TestPersonPlaceRelation:
    def test_str(self):
        goitein = Person.objects.create()
        Name.objects.create(name="S.D. Goitein", content_object=goitein)
        philadelphia = Place.objects.create()
        Name.objects.create(name="Philadelphia", content_object=philadelphia)
        (home_base, _) = PersonPlaceRelationType.objects.get_or_create(name="Home base")
        relation = PersonPlaceRelation.objects.create(
            person=goitein,
            place=philadelphia,
            type=home_base,
        )
        assert str(relation) == f"{home_base} relation: {goitein} and {philadelphia}"


@pytest.mark.django_db
class TestDocumentPlaceRelation:
    def test_str(self):
        fustat = Place.objects.create()
        Name.objects.create(name="Fustat", content_object=fustat)
        (letter_origin, _) = DocumentPlaceRelationType.objects.get_or_create(
            name="Letter origin"
        )
        doc = Document.objects.create()
        relation = DocumentPlaceRelation.objects.create(
            place=fustat,
            document=doc,
            type=letter_origin,
        )
        assert str(relation) == f"{letter_origin} relation: {doc} and {fustat}"


@pytest.mark.django_db
class TestPlacePlaceRelation:
    def test_str(self):
        fustat = Place.objects.create()
        Name.objects.create(name="Fustat", content_object=fustat)
        other = Place.objects.create()
        Name.objects.create(name="tatsuF", content_object=other)
        (possible_dupe, _) = PlacePlaceRelationType.objects.get_or_create(
            name="Possibly the same place as"
        )
        relation = PlacePlaceRelation.objects.create(
            place_a=fustat,
            place_b=other,
            type=possible_dupe,
        )
        assert str(relation) == f"{possible_dupe} relation: {fustat} and {other}"
        (neighborhood, _) = PlacePlaceRelationType.objects.get_or_create(
            name="Neighborhood", converse_name="City"
        )
        relation = PlacePlaceRelation.objects.create(
            place_a=fustat,
            place_b=other,
            type=neighborhood,
        )
        assert (
            str(relation)
            == f"{neighborhood.name}-{neighborhood.converse_name} relation: {fustat} and {other}"
        )


@pytest.mark.django_db
class TestEvent:
    def test_str(self):
        event = Event.objects.create(name_en="PGPv4 released")
        assert str(event) == event.name

    def test_date_str(self, document):
        event = Event.objects.create()
        assert not event.date_str

        # should use standardized dates from associated docs
        document.events.add(event)
        document.doc_date_standard = "1000/1010"
        document.save()
        assert event.date_str == standard_date_display(document.doc_date_standard)

        # if defined, should use standard override date on event
        event.standard_date = "1000/1099"
        assert event.date_str == standard_date_display(event.standard_date)

        # if defined, should use display override date on event
        event.display_date = "ca. 11th century"
        assert event.date_str == event.display_date

    def test_documents_date_range(self, document, join):
        event = Event.objects.create()
        assert event.documents_date_range == ""

        # should populate from standardized dates and date ranges in associated docs
        document.events.add(event)
        document.doc_date_standard = "1100"
        document.save()
        assert event.documents_date_range == document.doc_date_standard
        document.doc_date_standard = "1100/1150"
        document.save()
        assert event.documents_date_range == document.doc_date_standard

        # should use the combined range between dating and standard date
        Dating.objects.create(
            document=document,
            display_date="",
            standard_date="1010/1050",
        )
        # sometimes these years will have leading 0s
        assert event.documents_date_range == "1010/1150"

        # should use the combined range between multiple documents
        event.documents.add(join)
        join.doc_date_standard = "1000/1010"
        join.save()
        assert event.documents_date_range == "1000/1150"


@pytest.mark.django_db
class TestPersonEventRelation:
    def test_str(self):
        goitein = Person.objects.create()
        Name.objects.create(name="Goitein", content_object=goitein)
        event = Event.objects.create(name="S.D. Goitein's first publication")
        relation = PersonEventRelation.objects.create(person=goitein, event=event)
        assert str(relation) == f"Person-Event relation: {goitein} and {event}"


@pytest.mark.django_db
class TestPlaceEventRelation:
    def test_str(self):
        fustat = Place.objects.create()
        Name.objects.create(name="Fustat", content_object=fustat)
        event = Event.objects.create(name="Founding of the Ben Ezra Synagogue")
        relation = PlaceEventRelation.objects.create(place=fustat, event=event)
        assert str(relation) == f"Place-Event relation: {fustat} and {event}"


@pytest.mark.django_db
class TestPlaceSignalHandlers:
    @patch.object(ModelIndexable, "index_items")
    def test_related_save(self, mock_indexitems, person, document):
        place = Place.objects.create()

        # unsaved name should be ignored
        name = Name(name="test name")
        PlaceSignalHandlers.related_save(Name, name)
        mock_indexitems.assert_not_called()
        # raw - ignore
        PlaceSignalHandlers.related_save(Name, name, raw=True)
        mock_indexitems.assert_not_called()
        # name associated with a place
        name.content_object = place
        name.save()
        PlaceSignalHandlers.related_save(Name, name)
        assert mock_indexitems.call_count == 1
        assert place in mock_indexitems.call_args[0][0]

        # person place relation
        ppr = PersonPlaceRelation(person=person, place=place)
        ppr.save()
        mock_indexitems.reset_mock()
        PlaceSignalHandlers.related_save(PersonPlaceRelation, ppr)
        assert mock_indexitems.call_count == 1
        assert place in mock_indexitems.call_args[0][0]

        # document place relation
        dpr = DocumentPlaceRelation(document=document, place=place)
        dpr.save()
        mock_indexitems.reset_mock()
        PlaceSignalHandlers.related_save(PersonPlaceRelation, dpr)
        assert mock_indexitems.call_count == 1
        assert place in mock_indexitems.call_args[0][0]

        # unhandled model should be ignored, no error
        mock_indexitems.reset_mock()
        PlaceSignalHandlers.related_save(Place, place)
        mock_indexitems.assert_not_called()

    @pytest.mark.django_db
    @patch.object(ModelIndexable, "index_items")
    def test_related_delete(self, mock_indexitems, document):
        # delegates to same method as save, just check a few cases

        # Name associated with a document
        place = Place.objects.create()
        name = Name(name="test name", content_object=place)
        name.save()
        # delete
        mock_indexitems.reset_mock()
        PlaceSignalHandlers.related_delete(Name, name)
        assert mock_indexitems.call_count == 1
        assert place in mock_indexitems.call_args[0][0]

        # document place relation
        dpr = DocumentPlaceRelation(document=document, place=place)
        dpr.save()
        mock_indexitems.reset_mock()
        PlaceSignalHandlers.related_delete(DocumentPlaceRelation, dpr)
        assert mock_indexitems.call_count == 1
        assert place in mock_indexitems.call_args[0][0]
