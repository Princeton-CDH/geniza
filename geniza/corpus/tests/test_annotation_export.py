import logging
import os
from io import StringIO
from unittest.mock import Mock, patch

import pytest
from django.test import TestCase, override_settings

from geniza.corpus.annotation_export import AnnotationExporter


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


# todo set override configs


@override_settings(
    ANNOTATION_BACKUP_PATH="/tmp/anno-export",
    ANNOTATION_BACKUP_GITREPO="git:ghub.org/repo.git",
)
@patch("geniza.corpus.annotation_export.Repo")
def test_setup_repo_existing(mock_repo, tmp_path):
    anno_ex = AnnotationExporter()
    # setup when directory already exists
    remote_git_url = "git:somewhere.co/repo.git"
    local_path = str(tmp_path)
    # os.makedirs(local_path, exist_ok=True)
    anno_ex.setup_repo(local_path, remote_git_url)

    # not called since it already exists
    assert mock_repo.clone_from.call_count == 0
    mock_repo.assert_called_with(local_path)
    mock_repo.return_value.remotes.origin.pull.assert_called()


@override_settings(
    ANNOTATION_BACKUP_PATH="/tmp/anno-export",
    ANNOTATION_BACKUP_GITREPO="git:ghub.org/repo.git",
)
class TestAnnotationExporter(TestCase):
    @patch("geniza.corpus.annotation_export.Repo")
    def test_setup_repo_new(self, mock_repo):
        anno_ex = AnnotationExporter()
        # setup when directory doesn't exist
        local_path = "/tmp/my/repo/path"
        remote_git_url = "git:somewhere.co/repo.git"
        anno_ex.setup_repo(local_path, remote_git_url)

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


def test_output_message_logger(caplog):
    # use caplog fixture to inspect logger
    anno_ex = AnnotationExporter()

    with caplog.at_level(logging.DEBUG):
        anno_ex.output_message("debug message", logging.DEBUG)
    assert "debug message" in caplog.text

    with caplog.at_level(logging.WARNING):
        anno_ex.output_message("info message", logging.INFO)
    assert "info message" not in caplog.text
