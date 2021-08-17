# Change Log

## 0.4.0

* As a content editor, I would like to input dates in a separate field, so that both content editors and site users can sort and filter documents by date.
* As a content editor, I want to import fragment view and IIIF urls from a csv file into the database so that I can provide access to images for fragments.
* As a content editor, I want to be able to filter documents by library, so that I can narrow down clusters of documents and perform other research and data tasks
* As a content editor, I want to search documents by combined shelfmark without removing the + so I can quickly find documents that are part of joins.
* As a user, I want to search documents by keyword or phrase so that I can find materials related to my interests.
* As a user, I want to see updates and changes made in the new database in the current pgp site while the new website is still in development so that I can reference current information.
* bugfix: Fragment reassociation doesn't update the search index
* bugfix: Sorting fragments by collection raises a 500 error
* bugfix: admin document csv export has wrong date for first input
* bugifx: 500 error when trying to create a new document in the admin
* removed code related to import

## 0.3.0

* As a Global Admin, I want new documents created in the database after data import to receive PGPIDs higher than the highest imported PGPID, so that identifiers will be unique and semi-sequential.
* As a Global Admin, I want documents associated with language+script based on display name when importing documents from metadata spreadsheet.
* As a Global Admin, I want display name included in the one-time import of languages and scripts, so that I can start using display names while the import is still being developed and tested.
* As a Global Admin, I want to import additional spreadsheets as part of the data import so that I can ensure demerged records are imported.
* As a Content Admin, I want notes and technical notes parsed and optionally imported into the database so I can preserve and act on important information included in those fields.
* As a Content Admin, I want book sections, unknown sources, translation language, and other information included in editor import so that more of the scholarship records are handled automatically.
* As a Content Admin, I want a one time import of a document's edit history to start building a history of who has worked on the document and when.
* As a Content Editor, I want to download a CSV version of all or a filtered list of sources in the backend, in order to data work or facilitate my own research.
* As a Content Editor, I want to download a CSV version of all or a filtered list of footnotes in the backend, in order to data work or facilitate my own research.
* As a Content Editor, I want scholarship records from known journals imported as articles even if no title is present, so I can identify the resources and augment them later.
* As a Content Editor, when editor and translator information is imported I want urls associated with the footnote so I can get to the resource if available.
* As a Content Editor, I want to use the Text Block area to mark shelfmarks that are potential joins without adding to the string of shelfmarks, so that we can connect related documents without certainty.
* As a Content Editor, I want to add and edit all footnotes associated with a single source to make bulk data entry easy and efficient.
* As a Content Editor, I want to see and sort on the footnote count for sources so that I can find out how many times a source has been referenced in the database.
* As a Content Editor, I want to view and search on PGPID so I can distinguish documents on the same shelfmark and refer to the same documents in the spreadsheet and database.
* As a Content Editor, I want to download a CSV version of all or a filtered list of documents in the backend, in order to data work or facilitate my own research.
* As a Content Editor, I want to see who first input a document and who last edited it, and when, so that I can ensure records are kept up-to-date.
* As a Content Editor I want to link a source to a document as a footnote, in order to show that the source is helpful for understanding the document.
* As a Content Editor, I want a one time import of the translator and editor information so I know which scholars have transcribed or translated a document. (first pass)
* As a Content Editor, I want to create and edit scholarship records so that I can keep track of relevant scholarship on documentary geniza fragments.
* As a Content Editor, I want to filter documents by those with at least one fragment image, so that I can create useful visual datasets for download and producing teaching materials.
* As a User, I want to view detailed information for a single Geniza document so that I can learn about that document.
