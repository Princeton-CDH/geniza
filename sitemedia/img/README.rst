Image organization
##################

This document explains how images are organized in the Princeton Geniza Project GitHub repository.

Uploading process
-----------------

Files may be uploaded directly to GitHub. However, if it is inefficient for designers to deal with the below organization, they may instead pass images to a developer (e.g. through Google Drive or Dropbox).

When uploading such image(s), the developer must include a blank line at the end of their commit message, followed by another line:

::

    Co-authored-by: name <name@example.com>


This co-author credit should include the name and email of the designer.

Filenames
---------

Files are named simply, with as few words as possible. When necessary, multiple words may be separated with a `simple hyphen <https://en.wikipedia.org/wiki/Hyphen-minus>`_ (``-``). Filenames may not contain any spaces, em or en dashes, or other special characters. In general, refrain from using non-alphanumeric characters.

Folders
-------

An image may be placed in one of the following subfolders of the ``img`` folder, depending on its intended usage:

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Name
     - Contents
   * - ``fixtures``
     - Placeholder images for fake/test content, used in Percy
   * - ``icons``
     - Icons, such as `favicons <https://developer.mozilla.org/en-US/docs/Glossary/Favicon>`_ and other web browser icons, that are *not* user interface elements
   * - ``logos``
     - Logo images, such as the PGP logo
   * - ``ui``
     - Images used in the user interface, such as separators, header and footer images

If an image does not fit into any of these categories, it may be placed into the ``img`` folder directly.

Structure of the ``logos`` and ``ui`` folders
---------------------------------------------

The ``logos`` and ``ui`` subfolders are structured in the following way:

::

    ui
    ├── all
    │   └── all
    │       └── search-filter-icon.svg
    ├── desktop
    │   ├── all
    │   │   ├── 404.png
    │   │   └── separator.svg
    │   ├── dark
    │   │   ├── all
    │   │   │   ├── footer-base.svg
    │   │   │   └── submenu-base.svg
    │   │   ├── ltr
    │   │   │   ├── header-base.svg
    │   │   │   └── header-image.png
    │   │   └── rtl
    │   │       ├── header-base.svg
    │   │       └── header-image.png
    │   └── light
    │       ├── all
    │       │   ├── footer-base.svg
    │       │   └── submenu-base.svg
    │       ├── ltr
    │       │   ├── header-base.svg
    │       │   └── header-image.png
    │       └── rtl
    │           ├── header-base.svg
    │           └── header-image.png
    └── mobile
        ├── all
        │   ├── 404.png
        │   └── separator.svg
        ├── dark
        │   ├── all
        │   │   ├── footer-base.svg
        │   │   └── footer-image.png
        │   ├── ltr
        │   │   ├── header-base.svg
        │   │   └── header-image.png
        │   └── rtl
        │       ├── header-base.svg
        │       └── header-image.png
        └── light
            ├── all
            │   ├── footer-base.svg
            │   └── footer-image.png
            ├── ltr
            │   ├── header-base.svg
            │   └── header-image.png
            └── rtl
                ├── header-base.svg
                └── header-image.png


There are three subfolders at the top level, ``desktop``, ``mobile``, and ``all`` to differentiate between UI elements used on different screen sizes. Elements used across both screen sizes may be placed in the ``all`` subfolder.

One level deeper, the ``dark`` and ``light`` subfolders differentiate between images used in dark mode and light mode themes. These ``dark`` and ``light`` subfolders are where images are placed.

If an image can be reused for both light and dark mode, either through SVG recoloring or simply because they are the same in both modes, they may be placed in the ``all`` subfolder.

Finally, if variants are needed for right-to-left (RTL) and left-to-right (LTR) reading languages, then a set of subfolders ``ltr``, ``rtl``, and ``all`` may be created at the deepest level, and images may be placed there according to intended reading direction.

Notes
~~~~~
- Images that are meant to be swapped out between screen sizes, or between dark/light themes, should have the **same filename** as each other. They are differentiated by their folder, rather than their filename.
- ``svg`` images that are filled with a solid color, such as ``separator.svg``, may optionally be placed in only one directory per screen size, as they can be recolored in CSS to the appropriate light or dark mode color.
- ``png`` images that are colored differently in light and dark mode must be uploaded in their appropriate folders, as they cannot be recolored in CSS.
