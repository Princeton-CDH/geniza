import logging
import os
from io import StringIO
from unittest.mock import Mock, patch

import pytest
from django.test import TestCase, override_settings

from geniza.corpus.annotation_export import AnnotationExporter
from geniza.corpus.models import Document


def test_transcription_filename(document, footnote):
    filename = AnnotationExporter.transcription_filename(document, footnote.source)
    # starts with pgpid id
    assert filename.startswith("PGPID%s" % document.pk)
    # includes source id
    assert "_s%d" % footnote.source.pk in filename
    # includes author last name slug
    assert "_%s_" % footnote.source.authors.first().last_name.lower() in filename
    assert filename.endswith("transcription")

    # test with no author
    footnote.source.authors.clear()
    filename = AnnotationExporter.transcription_filename(document, footnote.source)
    assert "_unknown-author_" in filename


# test input, expected results
canvas_uris_to_listname = [
    (
        "https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-00321-00008/canvas/1",
        "cudl_MS-TS-NS-00321-00008_canvas_1",
    ),
    (
        "https://figgy.princeton.edu/concern/scanned_resources/f9eb5730-035c-420a-bf42-13190f97c10d/manifest/canvas/cfd65bb6-7ff5-47e8-9e92-29dd0e05baf2",
        "figgy_cfd65bb6-7ff5-47e8-9e92-29dd0e05baf2",
    ),
    (
        # not exactly what these will look like
        "https://princetongenizalab.github.io/iiif/manifests/canvas/1.json",
        "princetongenizalab_manifests_canvas_1",
    ),
    (
        "https://digi.ub.uni-heidelberg.de/diglit/iiif/codheidorient78/canvas/0001",
        "heidelberg_codheidorient78_canvas_0001",
    ),
]


@pytest.mark.parametrize("test_input,expected", canvas_uris_to_listname)
def test_annotation_list_name(test_input, expected):
    assert AnnotationExporter.annotation_list_name(test_input) == expected


@override_settings(
    ANNOTATION_BACKUP_PATH="/tmp/anno-export",
    ANNOTATION_BACKUP_GITREPO="git:ghub.org/repo.git",
)
@patch("geniza.corpus.annotation_export.Repo")
def test_setup_repo_existing(mock_repo, tmp_path):
    # setup when directory already exists
    remote_git_url = "git:somewhere.co/repo.git"
    local_path = str(tmp_path)

    with override_settings(
        ANNOTATION_BACKUP_PATH=local_path, ANNOTATION_BACKUP_GITREPO=remote_git_url
    ):
        anno_ex = AnnotationExporter()
        anno_ex.setup_repo()

    # not called since it already exists
    assert mock_repo.clone_from.call_count == 0
    mock_repo.assert_called_with(local_path)
    mock_repo.return_value.remotes.origin.pull.assert_called()


@override_settings(
    ANNOTATION_BACKUP_PATH="/tmp/anno-export",
    ANNOTATION_BACKUP_GITREPO="git:ghub.org/repo.git",
)
@patch("geniza.corpus.annotation_export.Repo")
def test_setup_repo_existing_no_push(mock_repo, tmp_path):
    # with push changes turned off, directory exists
    local_path = str(tmp_path)

    with override_settings(ANNOTATION_BACKUP_PATH=local_path):
        anno_ex = AnnotationExporter(push_changes=False)
        anno_ex.setup_repo()

    assert mock_repo.clone_from.call_count == 0
    mock_repo.assert_called_with(local_path)
    mock_repo.return_value.remotes.origin.pull.assert_not_called()


@override_settings(
    ANNOTATION_BACKUP_PATH="/tmp/anno-export",
    ANNOTATION_BACKUP_GITREPO="git:ghub.org/repo.git",
)
class TestAnnotationExporter(TestCase):
    def test_init_required_settings(self):
        with override_settings(
            ANNOTATION_BACKUP_PATH=None, ANNOTATION_BACKUP_GITREPO=None
        ):
            with pytest.raises(Exception) as excinfo:
                AnnotationExporter()

            assert "required" in str(excinfo.value)

    @patch("geniza.corpus.annotation_export.Repo")
    def test_setup_repo_new(self, mock_repo):
        # setup when directory doesn't exist
        local_path = "/tmp/my/repo/path"
        remote_git_url = "git:somewhere.co/repo.git"

        with override_settings(
            ANNOTATION_BACKUP_PATH=local_path, ANNOTATION_BACKUP_GITREPO=remote_git_url
        ):
            anno_ex = AnnotationExporter()
            anno_ex.setup_repo()

        mock_repo.clone_from.assert_called_with(url=remote_git_url, to_path=local_path)
        mock_repo.assert_called_with(local_path)

    @patch("geniza.corpus.annotation_export.Repo")
    def test_commit_changed_files_nochanges(self, mock_repo):
        anno_ex = AnnotationExporter()
        anno_ex.base_output_dir = "data"
        files = ["data/anno/pgp23/1.json"]
        anno_ex.repo = mock_repo
        anno_ex.repo.is_dirty.return_value = False

        anno_ex.commit_changed_files(files)
        # called without base dir prefix path
        mock_repo.index.add.assert_called_with(["anno/pgp23/1.json"])
        assert mock_repo.index.commit.call_count == 0

    @patch("geniza.corpus.annotation_export.Repo")
    def test_commit_changed_files(self, mock_repo):
        anno_ex = AnnotationExporter()
        anno_ex.base_output_dir = "data"
        files = ["data/anno/pgp23/1.json"]
        anno_ex.repo = mock_repo
        anno_ex.repo.is_dirty.return_value = True

        anno_ex.commit_changed_files(files)
        # called without base dir prefix path
        mock_repo.index.add.assert_called_with(["anno/pgp23/1.json"])
        mock_repo.index.commit.assert_called_with("Automated data export from PGP")
        # with push changes true
        mock_repo.remote.assert_called_with(name="origin")
        mock_repo.remote.return_value.pull.assert_called()
        mock_repo.remote.return_value.push.assert_called()

    def test_output_message_stdout(self):
        stdout = Mock()
        anno_ex = AnnotationExporter(stdout=stdout)

        anno_ex.verbosity = 0
        anno_ex.output_message("test", logging.DEBUG)
        stdout.write.assert_not_called()
        anno_ex.output_message("test", logging.INFO)
        stdout.write.assert_not_called()
        anno_ex.output_message("test", logging.WARN)
        stdout.write.assert_called()

    def test_output_message_shortcuts(self):
        anno_ex = AnnotationExporter()
        with patch.object(anno_ex, "output_message") as mock_output_msg:
            anno_ex.output_info("info")
            mock_output_msg.assert_called_with("info", logging.INFO)

            anno_ex.warn("warning")
            mock_output_msg.assert_called_with("warning", logging.WARNING)

            anno_ex.debug("debug")
            mock_output_msg.assert_called_with("debug", logging.DEBUG)

    def test_sync_github(self):
        anno_ex = AnnotationExporter()
        # use a Mock object for repo client
        anno_ex.repo = Mock()
        anno_ex.sync_github()

        # should get origin, pull, then push
        anno_ex.repo.remote.assert_called_with(name="origin")
        anno_ex.repo.remote.return_value.pull.assert_called()
        anno_ex.repo.remote.return_value.push.assert_called()

    def test_sync_github_no_origin(self):
        # sync if repository has no remote named origin
        anno_ex = AnnotationExporter()
        # patch warn method so we can inspect
        with patch.object(anno_ex, "warn") as mock_warn:
            # use a Mock object for repo client
            anno_ex.repo = Mock()
            anno_ex.repo.remote.side_effect = ValueError
            anno_ex.sync_github()

            mock_warn.assert_called_with("No origin repository, unable to push updates")


def test_output_message_logger(caplog, tmp_path):
    with override_settings(
        ANNOTATION_BACKUP_PATH=tmp_path, ANNOTATION_BACKUP_GITREPO="git:foo"
    ):
        # use caplog fixture to inspect logger
        anno_ex = AnnotationExporter()

        with caplog.at_level(logging.DEBUG):
            anno_ex.output_message("debug message", logging.DEBUG)
        assert "debug message" in caplog.text

        with caplog.at_level(logging.WARNING):
            anno_ex.output_message("info message", logging.INFO)
        assert "info message" not in caplog.text


@pytest.mark.django_db
@patch("geniza.corpus.annotation_export.Repo")
def test_annotation_export(mock_repo, annotation, tmp_path):
    # test actual export logic
    with override_settings(
        ANNOTATION_BACKUP_PATH=str(tmp_path), ANNOTATION_BACKUP_GITREPO="git:foo"
    ):
        doc_id = Document.id_from_manifest_uri(annotation.target_source_manifest_id)
        anno_ex = AnnotationExporter(pgpids=[doc_id])
        anno_ex.export()

        # should create document output dir
        doc_annolist_dir = tmp_path.joinpath("annotations", str(doc_id), "list")
        assert doc_annolist_dir.is_dir()
        # should create one annotation list json file
        anno_files = list(doc_annolist_dir.glob("*.json"))
        assert len(anno_files) == 1
        # inspect contents?

        # html and text directories should exist and should each have one file
        txt_transcription_dir = tmp_path.joinpath("transcriptions", "txt")
        assert txt_transcription_dir.is_dir()
        txt_files = list(txt_transcription_dir.glob("*.txt"))
        assert len(txt_files) == 1
        # should only have the content from the annotation
        assert txt_files[0].read_text() == "Test annotation"

        html_transcription_dir = tmp_path.joinpath("transcriptions", "html")
        assert html_transcription_dir.is_dir()
        html_files = list(html_transcription_dir.glob("*.html"))
        assert len(html_files) == 1
        html_content = html_files[0].read_text()
        assert "Test annotation" in html_content
        assert '<section dir="rtl"' in html_content

        # should commit changes
        anno_ex.repo.index.add.assert_called()
