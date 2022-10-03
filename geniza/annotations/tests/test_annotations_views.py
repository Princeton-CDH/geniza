import ast
import json
import uuid
from unittest.mock import patch

import pytest
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.urls import reverse
from parasolr.django.indexing import ModelIndexable
from pytest_django.asserts import assertContains, assertNotContains

from geniza.annotations.models import Annotation
from geniza.annotations.views import AnnotationResponse


@pytest.mark.django_db
class TestAnnotationList:

    anno_list_url = reverse("annotations:list")

    def test_get_annotation_list(self, client, annotation):
        anno1 = Annotation.objects.create(content={**annotation.content, "foo": "bar"})
        anno2 = Annotation.objects.create(content={**annotation.content, "baz": "qux"})

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

    def test_post_annotation_list_admin(self, admin_client, annotation):
        response = admin_client.post(
            self.anno_list_url,
            json.dumps({**annotation.content, "foo": "bar"}),
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


@pytest.mark.django_db
class TestAnnotationDetail:
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

    @patch.object(ModelIndexable, "index_items")
    def test_post_annotation_detail_admin(
        self, mock_indexitems, admin_client, annotation
    ):
        # update annotation with POST request as admin
        response = admin_client.post(
            annotation.get_absolute_url(),
            json.dumps({**annotation.content, "body": [{"value": "new text"}]}),
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

        # should have log entry for update
        log_entry = LogEntry.objects.get(object_id=annotation.id)
        assert log_entry.action_flag == CHANGE
        assert log_entry.change_message == "Updated via API"

    def test_post_annotation_detail_unchanged(self, admin_client, annotation):
        # update annotation unchanged with POST request as admin
        response = admin_client.post(
            annotation.get_absolute_url(),
            json.dumps({**annotation.content}),
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


@pytest.mark.django_db
class TestAnnotationSearch:
    anno_search_url = reverse("annotations:search")

    def test_search_uri(self, client, document, annotation):
        # content__target__source__id=target_uri)
        manifest_uri = reverse("corpus:document-manifest", kwargs={"pk": document.pk})
        target_uri = "http://example.com/target/1"
        anno1 = Annotation.objects.create(
            content={
                **annotation.content,
                "target": {
                    "source": {
                        "id": target_uri,
                        "partOf": {"id": manifest_uri},
                    }
                },
            }
        )
        anno2 = Annotation.objects.create(
            content={
                **annotation.content,
                "target": {
                    "source": {
                        "id": "http://example.com/target/2",
                        "partOf": {"id": manifest_uri},
                    }
                },
            }
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
        # content__contains={"dc:source": source_uri}
        manifest_uri = reverse("corpus:document-manifest", kwargs={"pk": document.pk})
        source_uri = source.uri
        anno1 = Annotation.objects.create(
            content={**annotation.content, "dc:source": source_uri}
        )
        anno2 = Annotation.objects.create(
            content={**annotation.content, "dc:source": twoauthor_source.uri}
        )
        anno3 = Annotation.objects.create(
            content={
                **annotation.content,
                "target": {
                    "source": {"id": source_uri, "partOf": {"id": manifest_uri}}
                },
            }
        )
        response = client.get(self.anno_search_url, {"source": source_uri})
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        # response should indicate annotation list
        assertContains(response, "sc:AnnotationList")
        # should bring back only anno1
        assertContains(response, anno1.uri())
        assertNotContains(response, anno2.uri())
        assertNotContains(response, anno3.uri())

    def test_search_manifest(self, client, source, document):
        # content__target__source__partOf__id=manifest_uri
        # within manifest
        anno1 = Annotation.objects.create(
            content={"target": {"source": {"partOf": {"id": document.manifest_uri}}}}
        )
        # no manifest
        anno2 = Annotation.objects.create(content={"dc:source": source.uri})
        response = client.get(self.anno_search_url, {"manifest": document.manifest_uri})
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        # response should indicate annotation list
        assertContains(response, "sc:AnnotationList")
        # should bring back only anno1
        assertContains(response, anno1.uri())
        assertNotContains(response, anno2.uri())

    def test_search_sort(self, client):
        anno3 = Annotation.objects.create(content={})
        anno10 = Annotation.objects.create(content={})
        anno1 = Annotation.objects.create(content={})
        anno2 = Annotation.objects.create(content={})

        # should return json AnnotationList with resources of length 4
        response = client.get(self.anno_search_url)
        assert response.status_code == 200
        results = response.json()
        assert "resources" in results and len(results["resources"]) == 4

        # in absence of schema:position, should order by created
        assert results["resources"][0]["id"] == anno3.uri()
        assert results["resources"][1]["id"] == anno10.uri()
        assert results["resources"][2]["id"] == anno1.uri()
        assert results["resources"][3]["id"] == anno2.uri()

        # now set schema:position to reorder
        anno3.set_content({"schema:position": 3})
        anno3.save()
        anno10.set_content({"schema:position": 10})
        anno10.save()
        anno1.set_content({"schema:position": 1})
        anno1.save()
        anno2.set_content({"schema:position": 2})
        anno2.save()

        response = client.get(self.anno_search_url)
        results = response.json()

        # results should respect schema:position order: 1, 2, 3, 10
        assert results["resources"][0]["id"] == anno1.uri()
        assert results["resources"][1]["id"] == anno2.uri()
        assert results["resources"][2]["id"] == anno3.uri()
        assert results["resources"][3]["id"] == anno10.uri()
        assert results["resources"][-1]["schema:position"] == 10
