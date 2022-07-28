# Deploy Notes

## 4.6.0

-   Run `python manage.py sync_transcriptions` to migrate transcription content to the new paged/chunked format needed for the new image+transcription panel. Any transcriptions that are not synced correctly should be edited on the footnote in Django Admin as needed.
-   Reindex content in Solr to show selected images based on document side information in search results: `python manage.py index`

## 4.5.0

-   Document date functionality in this release requires updating the Solr index. Run `python manage.py index` to reindex all content.
-   The `convert_dates` manage command should be run to clean up existing standardized dates for use with filtering and sorting. First run `python manage.py convert_dates update` to reconvert dates from supported calendars; then run `python manage.py convert_dates clean` to standardize non-standard formats that can be easily adjusted.
-   Run `python manage.py import_manifests` to import and link any manifests that are referenced by url but not cached or associated in the database with their corresponding fragments.
-   Re-import JTS Figgy IIIF manifests with `import_manifests` script to add urls based on case-insensitive shelfmark matches.
-   Run `python manage.py import_manifests --update --filter figgy` to retrieve provenance information from PUL manifests for JTS content.

## 4.4.0

-   This update requires Solr indexing changes (image filter, shelfmark override, etc.). Run `python manage.py index` to reindex all content.

## 4.2.1

-   This update includes Solr indexing changes (stripping html tags out of descriptions). Run `python manage.py index` to reindex all content.

## 4.2

-   This update includes Solr indexing changes (for boolean fields on digital edition, translation, and discussion). Run `python manage.py index` to reindex all content.
-   Anywhere that Node versions are being managed manually, Node should be upgraded to at 16.x, at least 16.14.0, and NPM to 7.x, at least 7.24.2.
-   Copy the new fonts `GretaSansH-Bold.woff2` and `GretaSansH-Regular.woff2` from the shared Google Drive folder "Geniza – woff files only" to `sitemedia/fonts`

## 4.1

-   This update includes Solr configuration and indexing changes. Once the Solr core has been updated, run `python manage.py index` to reindex all content (for IIIF image and label indexing).
-   If not all languages should be enabled on the public site, edit `settings/local_settings.py` to add the **PUBLIC_SITE_LANGUAGES** variable from `settings/local_settings.py.sample`. As noted in the sample file, its value should be either a list of language codes that comprise the subset of **LANGUAGES** desired for the public site, or undefined.
-   To enable Google Analytics for the production site, configure **GTAGS_ANALYTICS_ID** in local settings.
-   Run `python manage.py update_translation_fields` to copy existing document descriptions to the description_en translated field.
-   Run `python manage.py import_manifests --update` to update locally-cached manifests with the new attribution field.

## 4.0

-   Run `python manage.py sync_transcriptions` to update transcriptions for documents with multiple transcriptions
-   Run `python manage.py index` to reindex all content to update scholarship records counts and shelfmark indexing
-   Add all new fonts from the shared Google Drive folder "Geniza – woff files only" to `sitemedia/fonts`

## 0.8

-   In order to set up About menu structure, go into the Wagtail CMS admin. Create and publish a new Container Page as a child of the English home page ("The Princeton Geniza Project"), and give it a title "About" and slug "about".
    -   Once the Container Page is created, move all desired Content Pages into the Container Page as children (click "More" > "Move", click the right arrow button next to the home page, then click on the title of the Container page)
    -   Ensure that each Content Page is set up to appear in the menu ("Promote" > check "Show in menus"), then re-publish each one
-   This update includes Solr configuration and indexing changes. Once the Solr core/collection configuration has been updated, all content should be reindexed.

## 0.7

-   Update settings to configure **TEI_TRANSCRIPTIONS_LOCAL_PATH** for the deploy environment.
-   Run `python manage.py bootstrap_content -h HOSTNAME -p PORT` to create stub pages for all site content needed for main site navigation.
-   After running the boostrap content, in the Wagtail CMS, go to "Settings" -> "Locales" and choose each non-English language. Enable syncing to them from English. This should auto-populate each other locale with a new home page and set of subpages.
-   Run `python manage.py add_links` with a csv file exported from PGP v3 links database.
-   Run `python manage.py sync_transcriptions` to synchronize TEI transcription content to footnotes for search and display.
-   Solr indexing has changed significantly since the last release. All content should be reindexed: `python manage.py index`
-   Run `python manage.py import_manifests` to cache IIIF manifests in the database and link to fragment records.

## 0.3.0

-   Ensure that Django's default Site is configured with a valid hostname (e.g. test-geniza.cdh.princeton.edu)
-   Once the app has been deployed, execute the data import from Google Sheets using the `python manage.py import_data` command.
-   After the data import is complete, populate the search index using the `python manage.py index` command.
