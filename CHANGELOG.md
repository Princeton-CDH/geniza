# Change Log

## 4.0 — Initial public version of Princeton Geniza Project v4

-   public site
    -   As researcher, I want footnotes from the same source counted and displayed as a single scholarship record so that multiple links to parts of same document don't inflate the scholarship count and display.
    -   As a frontend user, I want all tags to be clickable so I can easily view all documents with those tags.
    -   As a front end user, I need to be able to see when more than 5 tags exist for search results because it's confusing to search for a tag and not see it displayed.
    -   As a front-end user, I should not be able to sort by relevance without any search text, since relevance is not meaningful without search terms.
    -   As a front end user, I want to see a homepage when I first visit the website so I can learn context for its contents.
    -   As a front end user, I want a transcription and image display that works on mobile devices, and allows me to zoom in and out on images.
    -   As an admin, I want the site to provide XML sitemaps for document and content pages so that site content will be findable by search engines
    -   As a long-time geniza researcher, I want links that I've bookmarked to redirect to the same content on the new version of the PGP site so I can access the documents I'm interested in. 🆕 enhancement
    -   various small improvements to document details page
-   content/data admin
    -   As a content admin, I want to easily see and sort documents that need review so that I can manage the queue more efficiently.
    -   As an admin, I want TEI transcription synchronization to handle documents with multiple transcriptions, so that content is not lost or hidden in the new system.
    -   As a content editor, I need to see volume for unpublished sources when editing footnotes so that I can select the correct source.
    -   bugfix: editing documents should not result in log entries linked to proxy document objects
    -   bugfix: django admin document filter by "has transcription" reports inaccurate numbers
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

-   maintenance/other
    -   Resolve failing lighthouse tests
    -   Updated versions of fonts

## 0.8

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

## 0.7

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

## 0.6

-   As a content editor, I want duplicate joined documents to be automatically merged without losing their unique metadata, so that I don't have to merge them manually.
-   Setup for webpack build for frontend scss/js assets and static files
-   bugfix: 500 error saving documents with footnotes (bad footnote equality check)

## 0.5

-   As a Content Editor, I want to see help text for Document Type so that I can make an informed decision while editing documents.
-   As a content editor, I want a one time consolidation of India Book sources so that the source list correctly represents the book volumes.
-   As a content editor, I want to be able to edit the Historic Shelfmark so that I can correct errors in the metadata.
-   As a content editor, I want to see admin actions beyond my most recent ten or a specific document's history, so that I can review past work.
-   As a user, I want to view detailed information about all the sources that cite this document so that I can learn the volume and kind of academic engagement with the document.
-   Rename document languages to primary languages and probable languages to secondary languages
-   Adopted isort python style and configured pre-commit hook

## 0.4

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

## 0.3

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
