Image organization
##################

This document explains how images are organized in the Princeton Geniza Project GitHub repository.

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
     - Logo images, such as the PGP logo; preferably in ``svg`` file format
   * - ``ui``
     - Images used in the user interface, see below for details

If an image does not fit into any of these categories, it may be placed into the ``img`` folder directly.

Structure of the ``ui`` folder
----------------------------

The ``ui`` subfolder contains images that are used in the user interface, such as separators, header and footer images, and custom quotation marks. The ``ui`` subfolder is structured in the following way:

::

    ui
    ├── desktop
    │   ├── dark
    │   │   ├── header-base.svg
    │   │   └── header-image.png
    │   └── light
    │       ├── header-base.svg
    │       ├── header-image.png
    │       └── separator.svg
    └── mobile
        ├── dark
        │   ├── header-base.svg
        │   └── header-image.png
        └── light
            ├── header-base.svg
            ├── header-image.png
            └── separator.svg

There are two subfolders at the top level, ``desktop`` and ``mobile``, to differentiate between UI elements used on different screen sizes. 

One level deeper, the ``dark`` and ``light`` subfolders differentiate between images used in dark mode and light mode themes. These ``dark`` and ``light`` subfolders are where images are placed.

Notes
~~~~~
- Images that are meant to be swapped out between screen sizes, or between dark/light themes, should have the **same filename** as each other. They are differentiated by their folder, rather than their filename.
- ``svg`` images that are filled with a solid color, such as ``separator.svg``, may optionally be placed in only one directory per screen size, as they can be recolored in CSS to the appropriate light or dark mode color
- ``png`` images that are colored differently in light and dark mode must be uploaded separately in their appropriate folders, as they cannot be recolored in CSS