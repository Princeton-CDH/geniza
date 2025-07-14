# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

import os
import sys

import django

sys.path.insert(0, os.path.abspath(".."))

os.environ["DJANGO_SETTINGS_MODULE"] = "geniza.settings"
django.setup()

from geniza import __version__

# -- Project information -----------------------------------------------------

project = "Princeton Geniza Project"
copyright = "2022, Center for Digital Humanities @ Princeton"
author = "The Center for Digital Humanities at Princeton"
description = "Django web application and other code for Princeton Geniza Project v4.x"


# The short X.Y version.
version = __version__
# The full version, including alpha/beta/rc tags.
release = __version__


# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",
    "sphinx.ext.coverage",
    "sphinx.ext.viewcode",
    "sphinx.ext.githubpages",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "alabaster"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

html_theme_options = {
    "description": description,
    "github_user": "Princeton-CDH",
    "github_repo": "geniza",
    "codecov_button": True,
}

html_sidebars = {
    "**": [
        "about.html",
        "navigation.html",
        "localtoc.html",
        "searchbox.html",
        "sidebar_footer.html",
    ],
}

# Configure for intersphinx for Python standard library, Django,
# and local dependencies with sphinx docs.
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "django": ("https://django.readthedocs.org/en/latest/", None),
    "djiffy": ("https://princeton-cdh.github.io/djiffy/", None),
    "viapy": ("https://viapy.readthedocs.io/en/latest/", None),
}


coverage_ignore_pyobjects = [
    # django auto-generated model methods
    "clean_fields",
    "get_deferred_fields",
    "get_(next|previous)_by_(created|last_modified|modified)",
    "refresh_from_db",
    "get_.*_display",  # django auto-generated method for choice fields
    "get_doc_relation_list",  # multiselectfield auto method
]

# Disable Sphinx 7.2+ coverage statistics, as this breaks CI
coverage_statistics_to_report = coverage_statistics_to_stdout = False
