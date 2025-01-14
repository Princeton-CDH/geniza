# Deploy Notes

## 4.19

-   Indexing logic has changed. Reindex all content: `python manage.py index`.

## 4.18.1

-   Metadata exports have been updated, and may require manually setting the
    last run date in `~/.pgp_export_lastrun` and running the management command
    `./manage.py export_metadata -w -s -v 2` to sync all data.

## 4.18

-   Solr configuration has changed. Ensure Solr configset has been updated
    and then reindex all content: `python manage.py index`

## 4.17

-   Solr configuration has changed. Ensure Solr configset has been updated
    and then reindex all content: `python manage.py index`
-   Configure **MAPTILER_API_TOKEN** in local settings for maps to appear.
-   Anywhere that Node versions are being managed manually, NPM should be upgraded to 8.x, at least 8.1.0.

## 4.16

-   Import Bodleian catalog numbers from a spreadsheet using the script
    `python manage.py add_cat_numbers spreadsheet.csv`, then reindex with
    `python manage.py index`.

## 4.15

-   The minimum required Solr version has been bumped to 9.2. Please upgrade to this version,
    update Solr configset, and then reindex all content with `python manage.py index`.

## 4.14

-   Seleucid calendar conversion is now implemented, so automatic conversion should be applied
    to all existing dates by using `python manage.py convert_dates update`.
-   Translation content is now indexed in search, so solr configuration has changed. Ensure Solr
    configset has been updated and then reindex all content: `python manage.py index`

## 4.13

-   Solr configuration has changed. Ensure Solr configset has been updated
    and then reindex all content: `python manage.py index`
-   The method for generating Bodleian IIIF manifests has changed. Run
    `python manage.py add_fragment_urls pgp-bodleian-manifests.csv --overwrite`
    against the latest copy of `pgp-bodleian-manifests.csv` from the
    `princetongenizalab/iiif` repo, then run `python manage.py import_manifests --update --filter "princetongenizalab.github.io/iiif/bodleian/"` to update cached manifests.

## 4.12

-   Before deploying, ensure that there is only one Digital Edition
    footnote per document and source combination. Otherwise, the
    annotation migration will fail.

## 4.11.1

-   Solr configuration has changed. Ensure Solr configset has been updated
    and then reindex all content: `python manage.py index`

## 4.11

-   Must configure **METADATA_BACKUP_GITREPO** and **METADATA_BACKUP_PATH** in local settings. These will determine locations for (respectively) the remote metadata repository (e.g. "https://github.com/Princeton-CDH/test-geniza-metadata") and the local files for the metadata exposts and syncing (e.g. "~/github/test-geniza-metadata").
-   For a cron job to backup metadata, try: `python manage.py export_metadata -ws -v 0`
    (i.e. Export metadata, making sure to write export files locally (`-w`) and sync those files to the remote repository (`-s`), while keeping a verbosity level of 0 (`-v 0`).)
-   Solr configuration has changed (change to description field).
    Ensure Solr configset has been updated and then reindex all
    content: `python manage.py index`

## 4.10

-   Solr configuration has changed. Ensure Solr configset has been updated
    and then reindex all content: `python manage.py index`

## 4.9.0

-   Must configure **ANNOTATION_BACKUP_PATH** and **ANNOTATION_BACKUP_GITREPO** in local settings. For proper setup, the directory at **ANNOTATION_BACKUP_PATH** should not exist when first run, but the containing directory should.
-   Load IIIF manifests for JRL Manchester content: download the csv at
    https://princetongenizalab.github.io/iiif/jrl/pgp-jrl-manifests.csv
    and run `python manage.py add_fragment_urls pgp-jrl-manifests.csv --overwrite --skip-indexing`
-   Load IIIF manifests for Bodleian content: download the csv at
    https://princetongenizalab.github.io/iiif/bodleian/pgp-bodleian-manifests.csv
    and run `python manage.py add_fragment_urls pgp-bodleian-manifests.csv --overwrite --skip-indexing`

-   Migrate transcription content from TEI xml to the new IIIF annotation
    format: `python manage.py tei_to_annotation -v 0`

.. Note:

The `sync_annotation_export` cron job should be _disabled_ while the migration is running,
to avoid the annotation backup git repository getting into a bad state.

-   Reindex after the migration: `python manage.py index`
-   Note: must manually accept GitHub host key the first time using annotation
    export to github
-   Configure `python manage.py sync_annotation_export` as a cron job to regularly
    update remote git repository with annotation exports generated via signal handler.
-   Copy the new fonts `WF-037420-012177-002520.woff`, `WF-037420-012177-002520.woff2`, and all `Amiri-*` and `Hassan*` from the shared Google Drive folder "Geniza – woff files only" to `sitemedia/fonts`
-   Copy the new versions of FrankRuhl, `FrankRuhl1924MF-Medium-Medium.woff` and `FrankRuhl1924MF-Medium-Medium.woff2` (note the dashes!) from the shared Google Drive folder "Geniza – woff files only" to `sitemedia/fonts`. There was an error with the original font's vertical metrics.
-   To enable the new warning banner, add the `FEATURE_FLAGS` list to local settings and populate it with the string `"SHOW_WARNING_BANNER"`. To change its contents, configure `WARNING_BANNER_HEADING` and `WARNING_BANNER_MESSAGE` in local settings.

## 4.8

-   Solr indexing has changed; reindex all content: `python manage.py index`

## 4.7.0

-   A tags migration in this release requires updating the Solr index. Run `python manage.py index` to reindex all content.
-   Run `python manage.py sync_transcriptions` to update transcription content to the latest format (linked to canvas URIs, skips non-document images).

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
