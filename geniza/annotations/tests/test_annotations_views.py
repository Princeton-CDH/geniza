import json
import uuid

import pytest
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.urls import reverse
from pytest_django.asserts import assertContains

from geniza.annotations.models import Annotation
from geniza.annotations.views import AnnotationResponse


@pytest.mark.django_db
class TestAnnotationList:

    anno_list_url = reverse("annotations:list")

    def test_get_annotation_list(self, client):
        anno1 = Annotation.objects.create(content={"foo": "bar"})
        anno2 = Annotation.objects.create(content={"baz": "qux"})

        response = client.get(self.anno_list_url)
        assert response.status_code == 200
        assertContains(response, anno1.uri())
        assertContains(response, anno2.uri())

    def test_post_annotation_list_guest(self, client):
        response = client.post(self.anno_list_url)
        # not logged in, should get permission denied error
        assert response.status_code == 403

    def test_post_annotation_list_admin(self, admin_client):
        response = admin_client.post(
            self.anno_list_url,
            json.dumps({"foo": "bar"}),
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
        assert anno.content == {"foo": "bar"}
        assert anno.created
        assert anno.modified

        # should have log entry for creation
        log_entry = LogEntry.objects.get(object_id=anno_id)
        assert log_entry.action_flag == ADDITION
        assert log_entry.change_message == "Created via API"


@pytest.mark.django_db
class TestAnnotationDetail:
    def test_get_annotation_detail(self, client):
        anno = Annotation.objects.create(content={"body": "some text"})
        response = client.get(anno.get_absolute_url())
        assert response.status_code == 200
        assert response.json() == anno.compile()
        assert response.headers["content-type"] == AnnotationResponse.content_type

    @pytest.mark.skip
    def test_get_annotation_notfound(self, client):
        # NOTE: failing because this currently redirects to /en/annotations/uuid/
        response = client.get(reverse("annotations:annotation", args=[uuid.uuid4()]))
        assert response.status_code == 404

    def test_post_annotation_detail_guest(self, client):
        # update annotation with POST request — fails if guest
        anno = Annotation.objects.create(content={"body": "some text"})
        response = client.post(
            anno.get_absolute_url(),
            json.dumps({"foo": "bar"}),
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_post_annotation_detail_admin(self, admin_client):
        # update annotation with POST request as admin
        anno = Annotation.objects.create(content={"body": "some text"})
        response = admin_client.post(
            anno.get_absolute_url(),
            json.dumps({"body": "new text"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        # should not match previous content
        assert response.json() != anno.compile()
        # get a fresh copy of the annotation from the database
        updated_anno = Annotation.objects.get(pk=anno.pk)
        # should match new content
        assert updated_anno.content["body"] == "new text"
        # updated content should be returned in the response
        assert response.json() == updated_anno.compile()

        # should have log entry for update
        log_entry = LogEntry.objects.get(object_id=anno.id)
        assert log_entry.action_flag == CHANGE
        assert log_entry.change_message == "Updated via API"

    def test_delete_annotation_detail_guest(self, client):
        # delete annotation with DELETE request — should fail if guest
        anno = Annotation.objects.create(content={"body": "some text"})
        response = client.delete(anno.get_absolute_url())
        assert response.status_code == 403

    def test_delete_annotation_detail_admin(self, admin_client):
        # delete annotation with DELETE request as admin
        anno = Annotation.objects.create(content={"body": "some text"})
        anno_id = anno.id
        response = admin_client.delete(anno.get_absolute_url())
        assert response.status_code == 204
        assert not response.content  # should be empty response

        # anno should be deleted from database
        assert not Annotation.objects.filter(pk=anno_id).exists()

        # should have log entry for removal
        log_entry = LogEntry.objects.get(object_id=anno_id)
        assert log_entry.action_flag == DELETION