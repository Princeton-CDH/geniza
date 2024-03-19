import json
import uuid

import pytest
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from geniza.annotations.models import Annotation
from geniza.annotations.views import AnnotationLastModifiedMixin, AnnotationResponse
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote, Source, SourceType


class TestAnnotationLastModifiedMixin:
    def test_get_etag(self, annotation):
        mixin = AnnotationLastModifiedMixin()
        # nonexistent annotation should return None
        assert mixin.get_etag(request=None, pk=1234) == None
        # otherwise should return ETag
        assert mixin.get_etag(request=None, pk=annotation.pk) == annotation.etag

    def test_get_last_modified(self, annotation):
        mixin = AnnotationLastModifiedMixin()
        # nonexistent annotation should return None
        assert mixin.get_last_modified(request=None, pk=1234) == None
        # otherwise should return last modified
        assert (
            mixin.get_last_modified(request=None, pk=annotation.pk)
            == annotation.modified
        )

    def test_disaptch(self, admin_client, annotation):
        # integration test for conditional response
        # get current etag
        old_etag = annotation.etag

        # change content
        annotation.content = {
            **annotation.content,
            "body": [{"value": "changed"}],
        }
        annotation.save()

        # attempt to update annotation with POST request as admin, including the old
        # ETag in If-Match header
        response = admin_client.post(
            annotation.get_absolute_url(),
            json.dumps(annotation.content),
            content_type="application/json",
            HTTP_IF_MATCH=old_etag,
        )
        # should result in 412 Precondition Failed status
        assert response.status_code == 412

        # attempt to delete annotation with DELETE request as admin, including the old
        # ETag in If-Match header
        response = admin_client.delete(
            annotation.get_absolute_url(), HTTP_IF_MATCH=old_etag
        )
        # should result in 412 Precondition Failed status
        assert response.status_code == 412


@pytest.mark.django_db
class TestAnnotationList:
    anno_list_url = reverse("annotations:list")

    def test_get_annotation_list(self, client, annotation):
        anno1 = Annotation.objects.create(
            footnote=annotation.footnote, content={**annotation.content, "foo": "bar"}
        )
        anno2 = Annotation.objects.create(
            footnote=annotation.footnote, content={**annotation.content, "baz": "qux"}
        )

        response = client.get(self.anno_list_url)
        assert response.status_code == 200
        # should include both annotations; confirm presence by uri
        assertContains(response, anno1.uri())
        assertContains(response, anno2.uri())

        response_data = response.json()
        # should include total
        assert response_data.get("total")
        # should include last modified
        assert response_data["modified"] == anno2.modified.isoformat()
        # should have type and label
        assert response_data["type"] == "AnnotationCollection"
        assert response_data["label"] == "Princeton Geniza Project Web Annotations"

        assertContains(
            response,
            "http://www.w3.org/ns/anno.jsonld",
            1,
            msg_prefix="annotation context should only be included once",
        )

    def test_post_annotation_list_guest(self, client):
        response = client.post(self.anno_list_url)
        # not logged in, should get permission denied error
        assert response.status_code == 403

    def test_post_annotation_list_malformed(
        self, admin_client, malformed_annotations, annotation_json
    ):
        # should raise 400 errors on bad JSON
        for json_dict in malformed_annotations:
            response = admin_client.post(
                self.anno_list_url,
                json.dumps(json_dict),
                content_type="application/json",
            )
            assert response.status_code == 400

        # for otherwise valid request but bad manifest URI, should raise 404 (Resolver404)
        response = admin_client.post(
            self.anno_list_url,
            json.dumps(
                {
                    **annotation_json,
                    "target": {
                        "source": {"partOf": {"id": "http://bad.com/documents/3/"}}
                    },
                }
            ),
            content_type="application/json",
        )
        assert response.status_code == 404

    def test_post_annotation_list_admin(self, admin_client, annotation_json):
        response = admin_client.post(
            self.anno_list_url,
            json.dumps(
                {
                    **annotation_json,
                    "foo": "bar",
                }
            ),
            content_type="application/json",
        )

        # admin has permission to create annotations
        assert response.status_code == 201  # created
        assert response.headers["content-type"] == AnnotationResponse.content_type
        # should return the newly created annotation as json
        content = response.json()
        # uri for new annotation should be set in Location header
        assert response.headers["location"] == content["id"]
        # new annotation returned with posted contents
        assert content["type"] == "Annotation"
        assert content["foo"] == "bar"

        # new annotation should be in database
        anno_id = content["id"].rstrip("/").split("/")[-1]  # get annotation id from uri
        anno = Annotation.objects.get(pk=anno_id)
        assert anno.content["foo"] == "bar"
        assert anno.created
        assert anno.modified

        # should have log entry for creation
        log_entry = LogEntry.objects.get(object_id=anno_id)
        assert log_entry.action_flag == ADDITION
        assert log_entry.change_message == "Created via API"

    def test_create_annotation(self, admin_client, document, source, annotation_json):
        # should create a DIGITAL_EDITION footnote if one does not exist
        assert not document.digital_editions().filter(source=source).exists()
        admin_client.post(
            self.anno_list_url,
            json.dumps(annotation_json),
            content_type="application/json",
        )
        # will raise error if digital edition footnote does not exist
        footnote = document.digital_editions().get(source=source)
        # since there was no corresponding Edition footnote with a Location, the
        # resulting digital footnote should not get a location
        assert not footnote.location

        # should log action
        assert LogEntry.objects.filter(
            object_id=footnote.pk, action_flag=ADDITION
        ).exists()


@pytest.mark.django_db
class TestAnnotationDetail:
    anno_list_url = reverse("annotations:list")

    def test_get_annotation_detail(self, client, annotation):
        response = client.get(annotation.get_absolute_url())
        assert response.status_code == 200
        assert response.json() == annotation.compile()
        assert response.headers["content-type"] == AnnotationResponse.content_type

    def test_get_annotation_notfound(self, client):
        response = client.get(reverse("annotations:annotation", args=[uuid.uuid4()]))
        assert response.status_code == 404

    def test_post_annotation_detail_guest(self, client, annotation):
        # update annotation with POST request — fails if guest
        response = client.post(
            annotation.get_absolute_url(),
            json.dumps({"foo": "bar"}),
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_post_annotation_detail_malformed(
        self, admin_client, malformed_annotations, annotation
    ):
        # should raise 400 errors on bad JSON
        for json_dict in malformed_annotations:
            response = admin_client.post(
                annotation.get_absolute_url(),
                json.dumps(json_dict),
                content_type="application/json",
            )
            assert response.status_code == 400

    def test_post_annotation_detail_admin(self, admin_client, annotation):
        # update annotation with POST request as admin
        # POST req must include manifest and source URIs
        anno_dict = {
            "body": [{"value": "new text"}],
            "target": {
                "source": {
                    "id": annotation.content["target"]["source"]["id"],
                    "partOf": {"id": annotation.target_source_manifest_id},
                }
            },
            "dc:source": annotation.footnote.source.uri,
            "motivation": "transcribing",
        }
        response = admin_client.post(
            annotation.get_absolute_url(),
            json.dumps(anno_dict),
            content_type="application/json",
        )
        assert response.status_code == 200
        # should not match previous content
        assert response.json() != annotation.compile()
        # get a fresh copy of the annotation from the database
        updated_anno = Annotation.objects.get(pk=annotation.pk)
        # should match new content
        assert updated_anno.content["body"] == [{"value": "new text"}]
        # updated content should be returned in the response
        assert response.json() == updated_anno.compile()

        # motivation should be matched to, or set on, associated Footnote as doc relation
        assert Footnote.DIGITAL_EDITION in updated_anno.footnote.doc_relation
        assert Footnote.DIGITAL_TRANSLATION not in updated_anno.footnote.doc_relation

        # should have log entry for update
        log_entry = LogEntry.objects.get(object_id=annotation.id)
        assert log_entry.action_flag == CHANGE
        assert log_entry.change_message == "Updated via API"

        # should match "translating" motivation to DIGITAL_TRANSLATION footnote
        response = admin_client.post(
            annotation.get_absolute_url(),
            json.dumps(
                {
                    **anno_dict,
                    "motivation": "translating",
                }
            ),
            content_type="application/json",
        )
        updated_anno = Annotation.objects.get(pk=annotation.pk)
        assert Footnote.DIGITAL_TRANSLATION in updated_anno.footnote.doc_relation

    def test_post_annotation_detail_unchanged(self, admin_client, annotation):
        # update annotation unchanged with POST request as admin
        # POST req must include manifest and source URIs
        response = admin_client.post(
            annotation.get_absolute_url(),
            json.dumps(
                {
                    **annotation.content,
                    "target": {
                        "source": {
                            "id": annotation.content["target"]["source"]["id"],
                            "partOf": {"id": annotation.target_source_manifest_id},
                        }
                    },
                    "dc:source": annotation.footnote.source.uri,
                }
            ),
            content_type="application/json",
        )
        assert response.status_code == 200
        # should match previous content, including last modified
        assert response.json() == annotation.compile()
        # get a fresh copy of the annotation from the database
        updated_anno = Annotation.objects.get(pk=annotation.pk)

        # should NOT have log entry for update
        assert not LogEntry.objects.filter(object_id=annotation.id).exists()

    def test_delete_annotation_detail_guest(self, client, annotation):
        # delete annotation with DELETE request — should fail if guest
        response = client.delete(annotation.get_absolute_url())
        assert response.status_code == 403

    def test_delete_annotation_detail_admin(self, admin_client, annotation):
        # delete annotation with DELETE request as admin
        anno_id = annotation.id
        response = admin_client.delete(annotation.get_absolute_url())
        assert response.status_code == 204
        assert not response.content  # should be empty response

        # anno should be deleted from database
        assert not Annotation.objects.filter(pk=anno_id).exists()

        # should have log entry for removal
        log_entry = LogEntry.objects.get(object_id=anno_id)
        assert log_entry.action_flag == DELETION
        # log entry change message should have details for export
        change_info = json.loads(log_entry.change_message)
        assert change_info["manifest_uri"] == annotation.target_source_manifest_id
        assert change_info["target_source_uri"] == annotation.target_source_id

    def test_delete_last_annotation(self, admin_client, annotation, annotation_json):
        # Should remove footnote DIGITAL_EDITION relation if deleted annotation
        # is the only annotation on source + document
        manifest_uri = annotation.target_source_manifest_id
        source_uri = annotation.footnote.source.uri
        source = Source.from_uri(source_uri)
        document = Document.from_manifest_uri(manifest_uri)
        # will raise error if digital edition footnote does not exist
        footnote = document.digital_editions().get(source=source)
        assert footnote.annotation_set.count() == 1
        admin_client.delete(annotation.get_absolute_url())
        # footnote should still exist, but no longer be a digital edition
        assert Footnote.objects.filter(object_id=document.pk, source=source).exists()
        assert not document.digital_editions().filter(source=source).exists()
        footnote.refresh_from_db()
        assert footnote.annotation_set.count() == 0
        assert Footnote.DIGITAL_EDITION not in footnote.doc_relation

        # Should not alter footnote doc_relation if there are more annotations on source + document
        # create two annotations
        for _ in range(2):
            admin_client.post(
                self.anno_list_url,
                json.dumps(annotation_json),
                content_type="application/json",
            )
        footnote = document.digital_editions().get(source=source)
        assert footnote.annotation_set.count() == 2
        # delete one of the annotations, footnote should still be digital edition
        admin_client.delete(footnote.annotation_set.first().get_absolute_url())
        document = Document.from_manifest_uri(manifest_uri)
        assert Footnote.DIGITAL_EDITION in footnote.doc_relation
        # document should still have a digital edition
        assert document.digital_editions().filter(source=source).exists()

    def test_delete_last_translation_anno(self, admin_client, translation_annotation):
        # Should remove footnote DIGITAL_TRANSLATION relation if deleted annotation
        # is the only annotation on source + document
        manifest_uri = translation_annotation.target_source_manifest_id
        source_uri = translation_annotation.footnote.source.uri
        source = Source.from_uri(source_uri)
        document = Document.from_manifest_uri(manifest_uri)
        # will raise error if digital translation footnote does not exist
        footnote = document.digital_translations().get(source=source)
        admin_client.delete(translation_annotation.get_absolute_url())
        # footnote should still exist, but no longer be a digital translation
        assert Footnote.objects.filter(object_id=document.pk, source=source).exists()
        assert not document.digital_translations().filter(source=source).exists()
        footnote.refresh_from_db()
        assert footnote.annotation_set.count() == 0
        assert Footnote.DIGITAL_TRANSLATION not in footnote.doc_relation

    def test_corresponding_footnote_location(self, admin_client, document):
        document_contenttype = ContentType.objects.get_for_model(Document)
        # create an Edition footnote on the document and source
        book = SourceType.objects.create(type="Book")
        source = Source.objects.create(source_type=book)
        Footnote.objects.create(
            doc_relation=[Footnote.EDITION],
            object_id=document.pk,
            content_type=document_contenttype,
            source=source,
            location="doc. 123",
        )
        # POST JSON to create a new annotation on the document and source
        anno_dict = {
            "body": [{"value": "new text"}],
            "target": {
                "source": {
                    "partOf": {"id": document.manifest_uri},
                }
            },
            "dc:source": source.uri,
            "motivation": "transcribing",
        }
        admin_client.post(
            self.anno_list_url,
            json.dumps(anno_dict),
            content_type="application/json",
        )
        # should not raise error because digital edition created by request
        created_digital_edition = Footnote.objects.get(
            doc_relation=[Footnote.DIGITAL_EDITION],
            source__pk=source.pk,
            content_type=document_contenttype,
            object_id=document.pk,
        )
        # should have its location copied from the existing Edition footnote
        assert created_digital_edition.location == "doc. 123"


@pytest.mark.django_db
class TestAnnotationSearch:
    anno_search_url = reverse("annotations:search")

    def test_search_uri(self, client, document, annotation, source):
        # content__target__source__id=target_uri)
        manifest_uri = reverse(
            "corpus-uris:document-manifest", kwargs={"pk": document.pk}
        )
        target_uri = "http://example.com/target/1"

        footnote = Footnote.objects.create(source=source, content_object=document)
        anno1 = Annotation.objects.create(
            footnote=footnote,
            content={
                **annotation.content,
                "target": {
                    "source": {
                        "id": target_uri,
                    }
                },
            },
        )
        anno2 = Annotation.objects.create(
            footnote=footnote,
            content={
                **annotation.content,
                "target": {
                    "source": {
                        "id": "http://example.com/target/2",
                    }
                },
            },
        )
        response = client.get(self.anno_search_url, {"uri": target_uri})
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        # response should indicate annotation list
        assertContains(response, "sc:AnnotationList")
        # should bring back only anno1
        assertContains(response, anno1.uri())
        assertNotContains(response, anno2.uri())

    def test_search_source(
        self, client, annotation, document, source, twoauthor_source
    ):
        # anno1 associated with source
        footnote = Footnote.objects.create(source=source, content_object=document)
        anno1 = Annotation.objects.create(footnote=footnote, content=annotation.content)
        twoauthor_footnote = Footnote.objects.create(
            source=twoauthor_source, content_object=document
        )
        # anno2 associated with two-author source
        anno2 = Annotation.objects.create(
            footnote=twoauthor_footnote, content=annotation.content
        )
        # anno3 also associated with two-author source
        anno3 = Annotation.objects.create(
            footnote=twoauthor_footnote,
            content=annotation.content,
        )
        response = client.get(self.anno_search_url, {"source": source.uri})
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        # response should indicate annotation list
        assertContains(response, "sc:AnnotationList")
        # should bring back only anno1
        assertContains(response, anno1.uri())
        assertNotContains(response, anno2.uri())
        assertNotContains(response, anno3.uri())

    def test_search_manifest(self, client, source, document, join):
        # associated with document based on footnote
        footnote = Footnote.objects.create(source=source, content_object=document)
        anno1 = Annotation.objects.create(
            footnote=footnote, content={"body": [{"value": "foo"}]}
        )
        # different document
        footnote2 = Footnote.objects.create(source=source, content_object=join)
        anno2 = Annotation.objects.create(footnote=footnote2, content=anno1.content)
        response = client.get(self.anno_search_url, {"manifest": document.manifest_uri})
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        # response should indicate annotation list
        assertContains(response, "sc:AnnotationList")
        # should bring back only anno1
        assertContains(response, anno1.uri())
        assertNotContains(response, anno2.uri())

    def test_search_sort(self, client, annotation):
        anno3 = Annotation.objects.create(
            footnote=annotation.footnote, content={"body": [{"value": "foo"}]}
        )
        anno10 = Annotation.objects.create(
            footnote=annotation.footnote, content=anno3.content
        )
        anno1 = Annotation.objects.create(
            footnote=annotation.footnote, content=anno3.content
        )
        anno2 = Annotation.objects.create(
            footnote=annotation.footnote, content=anno3.content
        )

        # should return json AnnotationList with resources of length 4
        response = client.get(self.anno_search_url)
        assert response.status_code == 200
        results = response.json()
        assert "resources" in results
        assert len(results["resources"]) == 5  # 4 plus fixture

        # in absence of schema:position, should order by created
        assert results["resources"][0]["id"] == annotation.uri()
        assert results["resources"][1]["id"] == anno3.uri()
        assert results["resources"][2]["id"] == anno10.uri()
        assert results["resources"][3]["id"] == anno1.uri()
        assert results["resources"][4]["id"] == anno2.uri()

        # now set schema:position to reorder
        anno3.set_content({**anno3.content, "schema:position": 3})
        anno3.save()
        anno10.set_content({**anno10.content, "schema:position": 10})
        anno10.save()
        anno1.set_content({**anno1.content, "schema:position": 1})
        anno1.save()
        anno2.set_content({**anno2.content, "schema:position": 2})
        anno2.save()
        annotation.set_content({**annotation.content, "schema:position": 5})
        annotation.save()

        response = client.get(self.anno_search_url)
        results = response.json()

        # results should respect schema:position order: 1, 2, 3, 5, 10
        assert results["resources"][0]["id"] == anno1.uri()
        assert results["resources"][1]["id"] == anno2.uri()
        assert results["resources"][2]["id"] == anno3.uri()
        assert results["resources"][3]["id"] == annotation.uri()
        assert results["resources"][4]["id"] == anno10.uri()
        assert results["resources"][-1]["schema:position"] == 10

    def test_search_motivation(self, client, annotation, translation_annotation):
        # motivation = transcribing
        response = client.get(
            self.anno_search_url,
            {"uri": annotation.target_source_id, "motivation": "transcribing"},
        )
        results = response.json()
        assert results["resources"][0]["id"] == annotation.uri()

        # motivation = translating
        response = client.get(
            self.anno_search_url,
            {"uri": annotation.target_source_id, "motivation": "translating"},
        )
        results = response.json()
        assert results["resources"][0]["id"] == translation_annotation.uri()
