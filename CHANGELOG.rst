Change Log
==========

4.17.3
------

- chore: Use self-hosted tinyMCE

4.17.2
------

- bugfix: Unable to rotate or reorder images in admin due to undefined rotation controls

4.17.1
------

- bugfix: Pin django-dbml to 0.7 and dbdocs to 0.8, until django-dbml supports dbdocs 0.9+

4.17
----

- public site
    - As a public site user, I would like to see date ranges separated with an en-dash (–) instead of an em-dash (—).
    - As a front end user, I only want to see one document number for a source displayed in the scholarship records on the public site.
    - As a frontend user, I want to see dating information displayed on document details when available, so that I can find out the time frame of a document when it is known.
    - bugfix: Double quotes search returning unexpected results
    - bugfix: Issues with shelfmark scoped search
    - bugfix: Highlighting context shows entire transcription or translation in search result
    - bugfix: Transcription search results not always formatted correctly
    - bugfix: Bracket and other character search is functioning unpredictably
    - bugfix: Incorrect words are highlighted in complete word quotation search (Hebrew script)
    - bugfix: Some partial search results in description not boosted by relevancy
    - chore: accessibility issues flagged by DubBot

- image, transcription, translation viewer/editor
    - As a transcription editor, I should see an error if I try to update an annotation with out of date content so that I don't overwrite someone else's changes.
    - bugfix: Autofill for source search (when inputting a transcription source) not functioning properly

- admin
    - As a content editor, I want to record places-to-places relationship on the place page and on the document detail page, so that I can track ambiguity.
    - As a content admin, I want to drop down a pin on a map and then be able to move the pin around so that I can manually adjust the coordinates of a place before saving the location.
    - As a content editor, I want there to be a notes field in the places pages so that I can add more detail about places that are hard-to-find.
    - As a content admin, I want a provenance field on the document detail page so that I can note the origin and aquisition history of fragments when available.
    - As a content editor, I want clearer help text for the name field of the person page so I know how best to present people's names on their pages
    - As a content editor, I would like to see Historic Shelfmark on the Document edit page, to ensure that my work is correct when working with old scholarship.
    - bugfix: Full shelfmark search for multiple shelfmarks not working in admin
    - bugfix: Invalid lat/long coordinates are allowed for Places, but don't persist
    - bugfix: People names are not diacritic neutral when adding them from Document Detail page

4.16.1
------

- bugfix: Add undefined check for OSD navigator

4.16
----

- public site
    - bugfix: Some records have Unicode non-breaking space
    - bugfix: Empty lines cause line number display issues in search results
    - bugifx: Indexing issues with creating documents in Hebrew or Arabic

- image, transcription, translation viewer/editor
    - bugfix: Some newly added transcriptions and translations misaligned
    - bugfix: Polygon annotation box requires hard refresh to start working (does not work immediately)
    - bugfix: Zoom thumbnail of document image in transcription editor behaving unpredictably
    - bugfix: Dark mode styles are broken for new transcription/translation source input

- admin
    - As a content editor, I want an option to include inferred dates in the admin date filter, so that they are included in CSV exports from filtered results.
    - As a content admin, I want to be able to merge two (identical) people pages without losing any data
    - As a content editor, I want to override the orientation of images displayed for a document so I can rotate images to display in logical orientation for readability/useability.
    - As a content admin, I want to add related documents directly from people pages to facilitate data entry.
    - bugfix: "PGPID OR PGPID" search does not work in the admin
    - bugfix: Cannot merge a document into a primary that does not have a description
    - chore: Automatic ingest of old/historic shelfmarks into the PGP for both backend and front end visibility

4.15.3
------

- bugfix: Last chosen person not populating in person-document relations dropdown

4.15.2
------

- bugfix: do not require browser in Google Docs ingest script

4.15.1
------

- bugfix: pin python dependency piffle==0.4 due to breaking change

4.15
----

- public site
    - bugfix: On tag change, document indexing is one revision behind
    - bugfix: Input date not always populating
    - bugfix: Digital translation footnote in scholarship records behaving incorrectly, excluding other footnotes on source

- image, transcription, translation viewer/editor
    - As a front end desktop user, I would like to see a bigger version of the document image in order to read the document (especially when no transcription exists).
    - As a public site viewer, I would like to see translation alongside the document image by default if both are present, so that I can read the document in my native language.
    - As a content editor, I want the "pop out" button in the transcription editor up higher, so it's immediately accessible.
    - As a content editor, I want the ability to add polygon annotation boxes using the transcription editor, so I can draw accurate bounding boxes around text.
    - As a content editor, I want the location field for digital edition/translations to automatically populate from an existing edition/translation on the same source, so that I can save time manually re-entering it.
    - bugfix: Editing/deleting parts of annotation box titles results in unexpected behavior (no change or deleting entire annotation box)
    - bugfix: In Safari, ITT panel toggles leave trails
    - bugfix: Annotations on the document detail page do not respect reordering
    - bugfix: Transcription and translation may become misaligned when resizing window
    - bugfix: Alignment between Arabic transcriptions and English translations is slightly off

- admin
    - As a content admin, I would like filters in the document admin to search by English and Hebrew language of translation, so that I can collect those documents for CSV export for use in teaching.
    - As a content admin, I would like to include a rationale for the inferred date field from a list of options, so that I can enter data more efficiently and consistently.
    - As a content admin, I want inferred date and accompanying notes in the csv exports of documents, so that I can keep track of this information in my own research.
    - As a content editor, I want a "no language" option when entering source languages (with help text) for unpublished transcriptions because the language will automatically be determined by the document languages already present on the doc detail pages.
    - As a content editor, I want clear help text when adding a source to explain how to select the source language, so that it is done consistently for translations and transcriptions.
    - As a content admin, I want both dates on document and inferred dates to merge when I merge duplicate PGPIDS so no data is lost when cleaning up duplicates. If there are two different dates on documents for the same PGPID, I want there to be an error message drawing my attention to the issue so I can choose the correct date or otherwise record the discrepancy.
    - As a content editor, I want a way to filter documents by date in the admin for enhanced csv exports
    - bugfix: Mixed inlines/formsets breaks on lack of permissions
    - bugfix: Merging two documents with digital content footnotes for the same source results in unique constraint violation

- people and places
    - As a content editor, I want a separate field to record people's names and roles in each document, so that I can build a structured dataset of all people across the PGP.
    - As a content editor, I want a separate field in the document detail page so that I can record place information mentioned in the document.
    - As a content editor, I want Person-Person relationship types visually sorted into their categories in the admin form, so that I can select them at a glance.
    - As a content admin, when adding people-to-people relationships in person pages, I want an added "ambiguity" category to the drop down so I can clarify when people are similar/not the same.
    - As a content admin, when viewing people-to-people relationships in person pages, I want reverse relationships to be visible, so that I don't inadvertently add a relationship twice.

4.14.2
------

- bugfix: fix tinyMCE text direction and API key instantiation

4.14.1
------

- bugfix: fix typo in permissions for tag merge

4.14
----

- public site
    - As a front end user, I want a translation module added to the image/transcription viewer so
      I can see translations of documents into my native language.
    - As a front-end user, I want to be able to search on the content of translations, so that I
      can find documents relating to terms that only appear within translations.
    - As a front-end user, I want transcription lines always aligned with translation lines when I
      view both, so that I can compare the two texts line-by-line.
    - bugfix: Dropdown header menu partially hidden behind search filters (z-index)

- admin
    - As a content editor, I want a way to track inferred dates for documents in a structured way
      so that it can be used for filtering, sorting, and display.
    - As a content editor, I want to filter the document list view to include translation (Y/N) in
      order to find translations
    - As a content editor, I want Seleucid dates automatically converted to standard dates when
      possible, so that dates can be compared and used for filtering and sorting
    - As a content editor, I want a translation module added to the transcription editor so I can
      add and edit translations to Geniza documents using the same interface as transcriptions.
    - As a content admin, I want translation backups to populate automatically in GitHub, alongside
      but differentiated from transcriptions, so that I can track changes in versioned translation
      content.
    - bugfix: Tags may be saved with identical names, case-insensitive
    - bugfix: Content Admins do not have correct permissions to merge tags

4.13
----

- public site
    - As a public site user, I want to be able to search descriptions for words/phrases in
      quotations, so that I can find exact matches for my search terms.
    - bugfix: Styles missing for JTS logo

- admin
    - As a content editor, I want to add transcriptions to documents without images in the PGP in
      the admin interface, so that I do not need to keep switching over to the public site to add
      transcriptions.
    - As a content editor working in the admin interface, I want a warning/error if I try to save
      a new document without a shelfmark.
    - As a content editor, I want a warning or validation to prevent adding more than one digital
      edition footnote for the same document source to avoid creating duplicates.
    - Prevent content editors from clicking more than one option for a digital edition, and explain
      to them the difference between edition and digital edition
    - As a content editor, I want the log entry to record and differentiate between users who input
      someone else's transcription versus users who created a new transcription so I can give the
      appropriate credit where it's due. 
    - As a content editor, I want to merge similar tags so I can consolidate redundant tags and
      decrease clutter in the database.
    - chore: Merge JTS and ENA collections
    - chore: Add help text to note section of footnote

- transcription editor
    - As content editor using the transcription editor, I want the image to be sticky so that I can
      always have the image beside the text as I scroll down.
    - Include two placeholder images for each fragment without images; give placeholder images
      unique labels corresponding to each fragment's shelfmark
    - bugfix: Clicking outside the current annotation zone and/or into another zone in the
      transcription editor cancels unsaved changes without warning
    - bugfix: Updated transcriptions failing to populate in search index

- iiif
    - bugfix: Some Bodleian iiif manifests were generated with incorrect shelfmarks
    - bugfix: Some JRL manifests say "recto" for the second image of a fragment

4.12
----

- Revise annotation model to link footnotes using foreign keys instead of URIs
- As a content editor working on transcriptions, I want to be able to move transcriptions from one document to another, so that I can fix a mistake if a transcription was associated incorrectly.
- bugfix: transcriptions can be orphaned or lost when merging records

4.11.1
------


- bugfix: Admin shelfmark search on "BL OR ..." gives too many and irrelevant results
- bugfix: Partial search in descriptions sorted by relevance not working well
- bugfix: Public site search of Latin script descriptions does not ignore diacritics and behaves unpredictably 
- bugfix: transcription labels in search results are RTL
- bugfix: transcription html/text export cleanup
- bugfix: some public metadata exports include empty columns for admin-only fields
- bugfix: 500 error on wagtail pages for a deleted page model


4.11
----

- As a frontend user, I want search results to include partial matches of phrases in descriptions sorted by relevance, so that I can search by incomplete phrases and view the closest matches first.
- As a content admin, I want document data exports synchronized to github so that there is a publicly accessible, versioned copy of project data available for researchers.
- As a content admin, I want fragment data exports available in django admin and synchronized to github so that there is a publicly accessible, versioned copy of project data available for researchers.
- As a content admin, I want scholarship records exported to github so that there is a publicly accessible, versioned copy of project data available for researchers.
- As a content admin, I want data exports to include information about who made edits when possible, so that I see who contributed to changes in project data.
- As a content editor, I want scholarship record summary information included in documents metadata so I can quickly see who has published on the document without switching context.
- As a content admin I would like to see counts and/or be able to export user log entries so that I can quantify how much work a content editor has contributed to the database.
- As a content editor, I want to view source URLs when I download the sources CSV in order to more easily find/update external sources.
- bugfix: search results don't always highlight matches in description text


4.10.1
------

- bugfix: annotation export script errors if manifest uri doesn't resolve
  to a valid document (handle deleted annotations on deleted documents)
- bugfix: documents in admin should be sorted by shelfmark by default

4.10
----

- public site
    - As a frontend user, I want search results to include partial matches of words in transcriptions, so that I can search by substrings of words.
    - As a front-end user, when I sort documents by shelfmark I want it sorted in logical, human-readable order instead of by string so that I can more easily find the records I'm interested in.
    - As a frontend user, I want keyword search for Seleucid dates to give me complete matches first so that I can browse by decreasing relevancy in the date field.
    - As a front end user who speaks Hebrew or Arabic, I want document types in search results in the currently active language, so that I can read and understand them.

- transcription editor
    - OpenSeadragon navigator should not be visible on placeholder images
    - As a content editor, I want commit messages for transcription export data on GitHub to include PGPID so that I can more easily find the changes I'm interested in.
    - bugfix: sometimes transcriptions changes appear not to save in the editor
    - bugfix: in transcription editor, there is no way to tell whether saving changes has succeeded or failed

- admin
    - As a content editor, I want the admin csv download to include transcription and translation indicators (Y/N) so that I can filter documents to those with or without transcription or translation.
    - As a content editor, I want database translation fields for Hebrew and Arabic content in the admin site to render text RTL, so that I can read and edit the content properly.
    - bugfix: In .csv downloads from the admin interface, for joins, the IIIF_url field needs a space after the semicolon.
    - bugfix: support for switching between multiple digital editions on a single document in admin version of image + transcription panel
    - transcription type styles in admin view

- maintenance/other
    - include ISSN in public site footer
    - accessibility: transcription content should have a lang attribute in html
    - design: implement the revised RTL mobile headers
    - upgrade to python 3.9

4.9
---

*transcription migration and new transcription editor*

public site
~~~~~~~~~~~

- As a content editor, I want transcription formatting preserved in search result display but ignored for search text so that I can see where in the transcription matching terms are.
- As a user, I want to see all transcription content for a document even if it extends beyond the currently available iiif images.
- As a frontend user, I want to search by partial shelfmarks so I can more easily find documents by exact shelfmark or groups of shelfmarks.
- As a frontend user, I want to be able to search by historic shelfmark so I can find documents by what they're called today.
- As a frontend user I want to search on document date information so I can find records by calendar or historic date.
- As a user, I want to see an image thumbnail when I'm zooming and panning on images, so that I can see what I'm looking at in the context of the whole image.
- bugfix: corrects a problem with Arabic script exact phrase searching

transcription editing
~~~~~~~~~~~~~~~~~~~~~

- As a content editor, I want to add block-level transcription to documents with images so that I can make existing transcription content available in the site.
As a user, when I’m reading transcription text, numbered lines should only wrap when necessary (based on display width), so that I can see more clearly how the lines match up with the original. #755
- As a content editor, I want to add and edit transcriptions on a separate page from the document detail or admin edit form, so that permissions and saving just the transcription can be managed more easily.
- As a content editor, I want transcription content linked to a scholarship record so that it is clearly documented who authored the transcription and where it came from.
- As a content editor I want to add or edit labels for blocks of transcription text so that I can indicate new sections or different kinds of texts.
- As a content editor I want to use basic formatting in transcription content so that I can enter lines as numbered lists or tag when the language changes within a document.
- As a transcription editor, I want to move transcription blocks to a different image so that I can easily correct content associated with the wrong image.
- As a transcription editor, I want to reorder transcription blocks within a page so that I can make sure text content matches logical document order.
- As a content editor, I want new and revised transcriptions available for search immediately so that changes and new content are all available to all site users.
- As a content editor, I want footnotes to indicate when a digital edition is available so that I can see and filter on records with and without transcription in the admin interface.
- As a content editor, I want to add and edit transcriptions for records without all IIIF images available so that transcriptions aren't limited to records with all images.
- As a transcription editor I want to edit and rearrange transcription content as numbered lists so that I can correct line wrapping introduced to match printed editions.
- As a content editor, I want to cut and paste transcription content from a Google Doc or similar and have it display properly with site styles so that I can easily add existing transcription content.


transcription migration and backup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- As an admin, I want transcription content synchronized from annotation storage to a GitHub repository so that the content is backed up, versioned, and available for use in generating a text corpus.
- As an admin I want TEI transcription content migrated to IIIF annotation so that I can manage and edit it in the new transcription editor.
- As a content admin, I want to add content editor user's github coauthor emails and link their account to scholarship records so that their contributions will be properly documented.
- As a content admin, I want TEI contributors documented in the new GitHub annotation and transcription backups so that there is a record of everyone who has contributed to the transcription structure and content.
- As a content admin, I want transcription content backups to be regularly updated as edits are made, so that the backup is up to date, version history is more granular, and I can compare changes.
- As a content admin, I want transcription backups to include information about who made edits when possible, so that I can track changes in versioned transcription content.
- As a content editor, I want to navigate the transcription export data on GitHub so that I can find exported content by PGPID.

design
~~~~~~

- Implement a language switch so that users can choose to view the site in English, Hebrew, or Arabic
- Implement the Hebrew type styles


iiif
~~~~

This release includes scripts to generate iiif manifests for Bodleian and Manchester images and
support for importing and displaying those manifests.

- As a content admin, I want images from the Bodleian Genizah collection made available as IIIF so they can be displayed on the site and be linked to transcription text.
- As a content admin, I want IIIF from the Manchester JRL Genizah collection remixed to match our data model so that images can be displayed on the site and be linked to transcription text.

admin
~~~~~

- bugfix: In .csv downloads from the admin interface, for joins, the IIIF_url field needs a space after the semicolon.
- add a configurable warning banner that can be displayed during the TEI migration and then turned off
- As an admin/content editor, I want to see all the images associated with a document so that I can determine whether I need to associate more images, clone the record, etc.

accessibility
~~~~~~~~~~~~~

- remediate sort selection drop-down (interactive controls must not be nested)
- light/dark mode toggle is not inside a landmark (all page content should be contained by landmarks)
- about menu id is duplicated — same id used in both header and footer nav (ids must be unique)


4.8.1
-----

- bugfix: documents without images can't be edited in django admin (makes image order override optional in django admin)


4.8
---

- public site
    - As a front end user, I want results boosted that match the exact language of my search query so that I get results in the same language first.
    - As a frontend user, I want smart quotes to be converted to normal quotation marks so I can get exact phrase search results when I use them.
    - bugfix: improved handling for bidirectional text in the document search input

- content/data admin
    - As a content editor, I want to override the order images are displayed for a document so that I can set the images to display in logical order for joins.
    - bugfix: not possible to edit recto/verso information for fragments without images

- accessibility
    - fixed twitter links in footer (previously same text but different urls)

- other
  - footnote superscripts were removed from TEI transcriptions
  - scripts for generating and working with static iiif content

4.7
---

Includes new document "excluded images" display, as well as tagging improvements for content editors.

- public site
    - As a user viewing document details I want to see which images are not part of the document so that I understand which parts of the fragment are used for the current document.
    - As a user looking at images for a single document, I want easy access to documents on images from the same fragment that are not part of the current document.

- content/data admin
    - As a content editor I want to select images in the related fragment view in order to determine which images belong with the document.
    - As a content editor, when I search for tags to add to a document I want the search to ignore case so that I don't create variations of the same tag.
    - As a content editor, I want to be able to search for tags with or without diacritics and get the same results.
    - refined logic for identifying transcription chunks that indicate new image for ``sync_transcriptions`` script

- visual design
    - Implement the light/dark mode toggle so that users can use the site in the UI mode they prefer.

4.6
---

Includes new image+transcription panel display.

- public site
   - As a user I want to toggle content panels so that I can view image or transcription separately or both at the same time, so I can read the content I am interested in.
   - As a user I want to see all images and first available transcription for a document, so that I can see and read the content.
   - As a user I want content panel toggles to be disabled when a record type for a document is not available, so that I know what content is available.
   - As a user I want to see page side and shelfmark information above each image so that I know what part of the document I’m viewing.
   - As a user I want to find image source and permissions within the image+transcription panel so that I can find out where fragment images come from and how I can use them.
   - As a user, I want the full citation for a transcription in context so I know who authored it and where it came from.
   - As a user I want to click or tap on image controls to turn on deep zoom so I can inspect the image in more detail.
   - As a desktop user, I want to click to rotate the deep zoom image of a fragment so that I can view it in alternate orientations.
   - As a desktop user, I want an angle control to rotate the deep zoom image of a fragment, so that I can control the rotation more finely than 90º increments.
   - As a user, when I search for a document that is only on one side of a fragment, I want to see the relevant image first so that I can preview the document more accurately.

- content/data admin
    - On the admin site, I want the tag list view to include counts for how many times its used, in order to understand the scope of tags and clean them.
    - As a content editor, when I select a fragment “side” in the document edit form I want an indicator of which fragment images will be displayed so that I can confirm I’m selecting the correct side or sides.
    - As an admin, I want TEI transcription synchronization to ignore documents that only contain labels, so that transcription content is prioritized over "see other" labels.
    - As a content editor, I want to view and edit transcription edit synced from TEI so that I can correct or remove incorrectly synced content when necessary.
    - bugfix: admin footnote download results in an empty csv file (headers only)

- visual design
    - bugfix: dark mode header display corrected for wide displays
    - revise tags display to match larger tap target for accessibility
    - change text in dark mode to not be pure white, for accessibility

4.5
---

- public site

  - As a user when viewing a document I want to see if there are any related documents so that I can easily discover other documents on the same shelfmarks.
  - As a front end user, I want to filter documents by date so that I can find documents known to be from a particular time period.
  - As a front-end user, I want to sort documents by document date so I can find the oldest or newest records within my search results when document date is known.
  - As a user, I would like to see historic and converted dates in document search results so that I can easily scan date information when it is known.
  - As a frontend user, I would like to see converted dates displayed in a standard, readable format so that I can easily understand the calendar information.
  - As a front-end user, I want to see provenance information for images when available so that I know where images and content is coming from for various shelfmarks.
  - As a frontend user, I want document descriptions displayed with line breaks from the content editors so that I can more easily read longer or more structured descriptions.
  - bugfix: sort should not automatically switch to relevance when the search term is revised
  - bugfix: server error for documents associated with Heidelberg IIIF (PGPIDs 34016, 34017, 34018)

- content/data admin

  - As a content editor, I want to see other documents on the same fragment as part of a document detail view in order to ensure I'm not creating a duplicate description.
  - As a content editor, I want Anno Mundi dates automatically converted to standard dates when possible, so that dates can be compared and used for filtering and sorting.
  - As a content editor, I want Hijrī dates automatically converted to standard dates when possible, so that dates can be compared and used for filtering and sorting.
  - As an content editor, I want the Document original date and calendar to be required together, so that I cannot produce incomplete records.
  - As a content editor, I want standard document dates validated so that I am prevented from entering dates the system can't use for searching and display.
  - As a content editor, I want standardized dates entered before validation was applied automatically cleaned up so they can be used for filtering and sorting in the public site.
  - As a content editor, I want fragment url importing to ignore upper/lower case differences when matching shelfmarks, so that I can import urls when the shelfmarks don't match exactly.
  - bugfix: improve language autocomplete search options on document edit form
  - bugfix: improve speed of language autocomplete on document edit form
  - bugfix: search for sources in admin interface doesn't include volume field
  - bugfix: spurious error message about caching failure when adding IIIF URLs to Fragment records
  - chore: automatically clean redundant manifest uris generated by some iiif viewers

- visual design

  - implement the search results page in RTL orientation for Hebrew and Arabic

4.4.1
-----

- bugfix: nav menu button light/dark toggle overlapping on tablet/mobile

4.4
---

-   public site

    - As a front end user, I want a filter for documents that have images, so that I can limit results to documents where I'll have ready access to visuals of the fragments.
    -   As a front-end user, I want to sort documents by shelfmark so that I can view records organized based on owning institution and/or collection.
    -   As a front-end user, I want to sort documents by input date so I can find the most recently added records or those that have been in PGP the longest.
    -   As a frontend user, I want to search in Arabic script and get search results from both Arabic and Judaeo-Arabic transcriptions so that I can find more content that matches my search.
    -   As a user, I would like to see historic and converted dates on the document details page so that I can easily find date information when it is known.
    -   As a front-end user, I want to see logos for museums and libraries providing image content, so I have a better sense of where the content is coming from.
    -   As a front-end user, I want a way to access the museum or library view of the fragment (when available), so I can see more context about the source.
    -   As a user, I want documents that span fragments with consecutive shelfmarks to have their shelfmark displayed using a range, so that it's easier for me to read.
-   content/data admin

    - As a content editor, when I'm editing a source I want footnotes sorted by location so I can review them in the same order they appear in the source.
    - As an admin user in document view, I'd like to be able to zoom on the fragment's IIIF image thumbnail so I can determine the language and check other metadata details as I'm writing or editing a description.
    - bugfix: Bad Request 400 when trying to move attachments
    - bugfix: Long lines in transcriptions break layout in admin interface


-   public site visual design

    -   RTL search form for light and dark mode for desktop and mobile
    -   logotype files in the header for the Hebrew site
    -   revised document detail view fields on top of the page on desktop and mobile
    -   revised image permissions statement
    -   flipped order of tabs for RTL
    -   Revise the placement of the burger menu on mobile so that it's on the opposite side from the logotype
    -   RTL footer designs for light and dark mode for desktop and mobile
    -   revised header styles
    -   homepage banner for light and dark mode for desktop and mobile
    -   site header for the Hebrew site
    -   pagination for the hebrew site

-   maintenance/other

    -   Resolve issue with Percy sporadically failing to load fonts
    -   Set up autogenerated python code documentation

4.3.1
-----

-   bugfix: edit link on public document detail page wasn't loading correctly due to Turbo

4.3
---

-   public site
    -   As a front-end user, I want the document search to automatically reload when I change my search terms, filters, or other options so that I can see the changed results more quickly.
    -   As a frontend user, I want to see primary and secondary languages when they've been assigned so that I have access to the known information about the document.
    -   As a frontend user, I want to easily find other documents on the same fragment in order to better interpret the images and gain context.
    -   As a frontend user, I want to easily select shelfmarks on the document detail page, so that I can copy and paste that information elsewhere.
-   content/data admin
    -   As a content editor, I want to add SVG images to content pages so that I can include data visualizations and other scalable images.
-   public site visual design
    -   implement tabs for Hebrew / RTL
    -   wider search results on mobile when search result numbering is lower
-   maintenance/other
    -   Implement Turbo to improve internal link speed
    -   refactor all JS to Stimulus

4.2.1 — bugfix release
----------------------

-   handle descriptions with tags so they don't cause malformed HTML in search results
-   last modified header should not be set for document search if sort is random
-   off-screen menu no longer shows up when resizing browser window or navigating on mobile
-   transcription lines should be right-aligned in admin interface
-   fix twitter/open graph title and description previews for wagtail pages

4.2
---

-   public site
    -   As a front-end user, I want keyword searches automatically sorted by relevance, so that I see the most useful results first.
    -   As a user, I want an option to sort documents randomly so that I can easily discover documents I haven't looked at before.
    -   As a front-end user, I want visual indicators for filtering search results, in a separate panel from the main search functions, so that I know where they are and can easily ignore them if I do not want to filter.
    -   As a front end user, I want to filter search results to records with transcription available, so that I can easily find documents that have already been transcribed and will be easier for me to use.
    -   As a front end user, I want to filter search results to records with translations available, so that I can find documents that are easier for me to work on.
    -   As a front end user, I want to filter search results to records with discussion available, so that I can find documents with existing scholarly notes.
    -   As a front end user, I want an easy way to apply selected filters, so that I can filter results without closing the filters panel.
    -   As a front end user, I want to click on the document title in search results so I can get to the details more easily.
    -   As a user, when I share PGP urls I want to see previews on social media, Slack or other supported platforms so that the content is more engaging.
    -   As a frontend user, when a PGPID is referenced in a document description, I want it to link to the corresponding document so that I can easily access referenced documents.
-   content/data admin
    -   As an admin, I want documents automatically reindexed when I add or update scholarship records, so that database edits are immediately available in the public site.
    -   As a content editor, I want to add translations for document types to the database, in order to make the content more accessible to Hebrew and Arabic users of the public site.
-   public site visual design
    -   logotype in header for both dark and light modes
    -   selected state for scholarship records filters in search
    -   new site favicon based on the logo
-   maintenance/other
    -   As an admin, I want documents automatically reindexed when I add or update scholarship records, so that database edits are immediately available in the public site.
    -   last modified headers and conditional processing on document search and document detail pages
    -   bugfix: correct an invalid prefetch field in Document.items_to_index
    -   bugfix: search sort options dropdown shouldn't move following page content down
    -   bugfix: image viewer breaks on mobile for documents with images but no transcriptions

4.1
---

-   public site
    -   As a user, I want to see image thumbnails with search results when available, so that I can quickly see which records have images and what they look like.
    -   As a frontend user, I want my search terms to match variant forms of the words I enter so that I can find all related content.
    -   As a researcher, I want to see Goitein's unpublished editions labeled more clearly, so I'm not confused by the ambiguous title "typed texts".
    -   As a front end user, I want to see all transcriptions expanded by default when viewing a document so that I can easily access content when there are multiple transcriptions.
    -   As a front-end user, I want to know which images are associated with each attribution, so that I am not confused by a list of attributions at the image and transcription display.
-   content/data admin
    -   As a content editor, I want to merge document records without losing data so that I can combine records when I've identified duplicates or joins.
    -   As a content admin, I want to search for documents by transcription content so I can work with and export content based on transcription text.
    -   As a content admin, I want to be able to see which transcriptions belong with which footnote so I can manage the content properly.
    -   As a content admin, I want to see multiple transcriptions arranged horizontally on the document edit page, instead of vertically.
    -   increase footnote source field size in document edit page so the names and titles are visible
    -   As a content editor, I want to add alternate text and captions for images in Wagtail so that I can describe and present images more clearly.
    -   As a content editor, I want to be able to underline text in Wagtail pages so I can use formatting in the glossary.
    -   As a content editor, I want to a way to add Hebrew descriptions of documents to the document record, so that available information can be managed in the same place.
    -   As an admin, I want to configure which languages are available on the site without disabling them in the admin site, to avoid people accidentally receiving a partially-translated version of the site that isn't ready.
-   maintenance/other
    -   setup google analytics
    -   include software version in site footer

4.0
---

**Initial public version of Princeton Geniza Project v4.0**

-   public site
    -   As researcher, I want footnotes from the same source counted and displayed as a single scholarship record so that multiple links to parts of same document don't inflate the scholarship count and display.
    -   As a frontend user, I want all tags to be clickable so I can easily view all documents with those tags.
    -   As a front end user, I need to be able to see when more than 5 tags exist for search results because it's confusing to search for a tag and not see it displayed.
    -   As a front-end user, I should not be able to sort by relevance without any search text, since relevance is not meaningful without search terms.
    -   As a front end user, I want to see a homepage when I first visit the website so I can learn context for its contents.
    -   As a front end user, I want a transcription and image display that works on mobile devices, and allows me to zoom in and out on images.
    -   As an admin, I want the site to provide XML sitemaps for document and content pages so that site content will be findable by search engines
    -   As a long-time geniza researcher, I want links that I've bookmarked to redirect to the same content on the new version of the PGP site so I can access the same documents on the new site
    -   various small improvements to document details page
    -   bugfix: search for partial shelfmarks doesn't yield the expected results
-   content/data admin
    -   As a content admin, I want to easily see and sort documents that need review so that I can manage the queue more efficiently.
    -   As an admin, I want TEI transcription synchronization to handle documents with multiple transcriptions, so that content is not lost or hidden in the new system.
    -   As a content editor, I need to see volume for unpublished sources when editing footnotes so that I can select the correct source.
    -   bugfix: editing documents should not result in log entries linked to proxy document objects
-   public site visual design
    -   links in all states (hover, click, focus)
    -   template and styles for 404 not found error page
    -   template and styles for 500 server error page
    -   pagination links in all modes and interactions (hover, click, focus, disabled)
    -   buttons in all states (hover, click, focus, disabled)
    -   colors for light and dark mode
    -   tabs on document detail and scholarship records (hover, click, focus, disabled)
    -   site footer with a list of site menu items, licensing, accessibility, and links to social media
    -   header and main menu
    -   search form and search page interactions (hover, click, focus, disabled)
    -   Updated versions of fonts (extended character support)
    -   Improved fallback font styles
-   maintenance/other
    -   Resolve failing lighthouse tests
    -   Improve handling for IIIF content to work better with PUL/JTS materials

0.8
---

-   public site search and document display
    -   As a front-end user, I want to use fields in my keyword searches so I can make my searches more specific and targeted.
    -   As a front-end user, I want to see all shelfmarks associated with a document, so that I can identify and find the supporting information from its various sources.
    -   bugfix: suppressed documents shouldn't be included in public document search
    -   As a frontend user, I want all tags to be clickable so I can easily view all documents with those tags.
    -   As a scholar, I want to get a copy of transcription text so that I can easily reference it and use it elsewhere.
    -   As a front-end user, I want to be able to switch between dark and light mode manually with a toggle or button so that I am not stuck viewing the site in the mode that matches my OS preference.
-   content/data admin
    -   bugfix: permissions error trying to delete a document because it wants to delete the associated log entry
    -   As a content editor, I want to be able to manage pages and page order in the site navigation menu or about submenu, so that I can update the site as content changes.
    -   As a content admin, I want to add and edit page ranges in Source records so I can document where in a book or journal the content appears.
    -   bugfix: multi-word tags get broken up into single-word tags
    -   bugfix: django admin document filter by "has transcription" reports inaccurate numbers
-   public site visual design implementation
    -   header & main menu visuals and interactions
    -   search form styles and interactions
    -   fonts and type styles
    -   tab styles on document detail page
-   maintenance
    -   Removed add_links manage command from version 0.7 (one-time import)
    -   made percy visual review workflow opt-in to avoid paying for excessive screenshots
    -   image files used in site design organized in site media, and organization documented

0.7
---

-   document search
    -   As a user I would like to know explicitly when a search result does not have any scholarship records so that I don't have to compare with results that do.
    -   As a user I would like to see transcription excerpts in my search results so I can tell which records have a transcription and can see some of the content.
    -   As a user I would like to see which page I'm on when viewing search results and navigate between pages so I can see more results.
    -   As a user I would like to filter my search by document type so that I can view specific types of documents.
    -   As a user, I want to sort search results by the number of scholarship records so I can easily find documents with scholarly work available or that have not been written about.
    -   As a user, when I search on shelfmark I want to see documents associated directly with that fragment before documents that include the shelfmark in a description or notes, so I can easily find documents by shelfmark.
    -   As a user viewing search results, when my search terms occur in the description I want to see keywords in context so that I can see why the document was included in the search results.
    -   As a user, I want to see document titles that include shelfmark and type so I can distinguish documents at a glance.
-   document details
    -   As a user, if I try to access a document by an old PGPID, I want to be automatically redirected to the correct page so that I can find the record I'm looking for.
    -   As a user I would like to see a permalink for each document so that I can easily document, remember and share links.
    -   As a user I would like to see scholarship records for each document so that I can learn more about research that has been done about each document
    -   As a front-end user, I want to see brief citations in the Document Detail view, more concise than those in Scholarship Records.
    -   Scholarship reference citations should include language if it is specified and not English
    -   As a front-end user, I want to be able to quickly see the section a footnote is referencing in a particular source.
    -   As a user, I want to see images and transcription, if any, for all fragments associated with a document so I can see the full contents that are available.
-   As an admin, I want data from PGP v3 links database imported into the new database so that I can manage links from the main admin site.
-   As an admin, I want an easy way to get from the public document view to the edit view on the admin site, so I can make edits and correct errors.
-   As an admin, I want numeric footnote locations automatically prefixed with 'pp.' so the meaning of the numbers will be clear to public site users.
-   As an admin, I want TEI transcription content regularly synchronized to the new database so that transcriptions are updated with changes in the current system.
-   As a content editor, I want to create and edit content pages on the site so that I can update text on the site when information changes.
-   As a content editor, I want to to download a list of sources which have footnote “editions” so that we can determine which books have yet to be mined for transcriptions.
-   As a user, I want to change site language so that I can switch languages when I don't want to use the browser-detected default.
-   bugfix: scholarship counts should always be displayed in search results
-   bugfix: omit volume when outputting footnote/source string for unpublished sources (i.e. Goitein "typed texts")
-   Design and UI:
    -   Update sitewide type to use purchased fonts, new styles
    -   Implement sites styles for navigation on desktop and mobile
    -   Implement designs for search form
-   Configured Lighthouse CI testing with GitHub Actions
-   Implemented visual review workflow with Percy and GitHub Actions
-   Configured and applied `djhtml` commmit hook for consistent formatting in django templates

0.6
---

-   As a content editor, I want duplicate joined documents to be automatically merged without losing their unique metadata, so that I don't have to merge them manually.
-   Setup for webpack build for frontend scss/js assets and static files
-   bugfix: 500 error saving documents with footnotes (bad footnote equality check)

0.5
---

-   As a Content Editor, I want to see help text for Document Type so that I can make an informed decision while editing documents.
-   As a content editor, I want a one time consolidation of India Book sources so that the source list correctly represents the book volumes.
-   As a content editor, I want to be able to edit the Historic Shelfmark so that I can correct errors in the metadata.
-   As a content editor, I want to see admin actions beyond my most recent ten or a specific document's history, so that I can review past work.
-   As a user, I want to view detailed information about all the sources that cite this document so that I can learn the volume and kind of academic engagement with the document.
-   Rename document languages to primary languages and probable languages to secondary languages
-   Adopted isort python style and configured pre-commit hook

0.4
---

-   As a content editor, I would like to input dates in a separate field, so that both content editors and site users can sort and filter documents by date.
-   As a content editor, I want to import fragment view and IIIF urls from a csv file into the database so that I can provide access to images for fragments.
-   As a content editor, I want to be able to filter documents by library, so that I can narrow down clusters of documents and perform other research and data tasks
-   As a content editor, I want to search documents by combined shelfmark without removing the + so I can quickly find documents that are part of joins.
-   As a user, I want to search documents by keyword or phrase so that I can find materials related to my interests.
-   As a user, I want to see updates and changes made in the new database in the current pgp site while the new website is still in development so that I can reference current information.
-   bugfix: Fragment reassociation doesn't update the search index
-   bugfix: Sorting fragments by collection raises a 500 error
-   bugfix: admin document csv export has wrong date for first input
-   bugifx: 500 error when trying to create a new document in the admin
-   removed code related to import
-   Adopted black code style and configured pre-commit hook

0.3
---

-   As a Global Admin, I want new documents created in the database after data import to receive PGPIDs higher than the highest imported PGPID, so that identifiers will be unique and semi-sequential.
-   As a Global Admin, I want documents associated with language+script based on display name when importing documents from metadata spreadsheet.
-   As a Global Admin, I want display name included in the one-time import of languages and scripts, so that I can start using display names while the import is still being developed and tested.
-   As a Global Admin, I want to import additional spreadsheets as part of the data import so that I can ensure demerged records are imported.
-   As a Content Admin, I want notes and technical notes parsed and optionally imported into the database so I can preserve and act on important information included in those fields.
-   As a Content Admin, I want book sections, unknown sources, translation language, and other information included in editor import so that more of the scholarship records are handled automatically.
-   As a Content Admin, I want a one time import of a document's edit history to start building a history of who has worked on the document and when.
-   As a Content Editor, I want to download a CSV version of all or a filtered list of sources in the backend, in order to data work or facilitate my own research.
-   As a Content Editor, I want to download a CSV version of all or a filtered list of footnotes in the backend, in order to data work or facilitate my own research.
-   As a Content Editor, I want scholarship records from known journals imported as articles even if no title is present, so I can identify the resources and augment them later.
-   As a Content Editor, when editor and translator information is imported I want urls associated with the footnote so I can get to the resource if available.
-   As a Content Editor, I want to use the Text Block area to mark shelfmarks that are potential joins without adding to the string of shelfmarks, so that we can connect related documents without certainty.
-   As a Content Editor, I want to add and edit all footnotes associated with a single source to make bulk data entry easy and efficient.
-   As a Content Editor, I want to see and sort on the footnote count for sources so that I can find out how many times a source has been referenced in the database.
-   As a Content Editor, I want to view and search on PGPID so I can distinguish documents on the same shelfmark and refer to the same documents in the spreadsheet and database.
-   As a Content Editor, I want to download a CSV version of all or a filtered list of documents in the backend, in order to data work or facilitate my own research.
-   As a Content Editor, I want to see who first input a document and who last edited it, and when, so that I can ensure records are kept up-to-date.
-   As a Content Editor I want to link a source to a document as a footnote, in order to show that the source is helpful for understanding the document.
-   As a Content Editor, I want a one time import of the translator and editor information so I know which scholars have transcribed or translated a document. (first pass)
-   As a Content Editor, I want to create and edit scholarship records so that I can keep track of relevant scholarship on documentary geniza fragments.
-   As a Content Editor, I want to filter documents by those with at least one fragment image, so that I can create useful visual datasets for download and producing teaching materials.
-   As a User, I want to view detailed information for a single Geniza document so that I can learn about that document.
