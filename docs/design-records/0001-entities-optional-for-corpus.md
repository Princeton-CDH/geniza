# 1. Make `geniza.entities` optional for `geniza.corpus`

-   **Status:** Accepted (implementation in progress)
-   **Date:** 2026-11-12

## Context

We want to reuse `geniza.corpus` in new projects that don't install `geniza.entities`.

Currently the two apps depend on each other:

-   `entities` depends on `corpus`. `entities/models.py` imports `Document`, `Dating`, `LanguageScript`, `PermalinkMixin` and `DisplayLabelMixin` from `corpus.models`. This direction is fine.
-   `corpus` also depends on `entities`, in several places:
    -   **Migrations:** `corpus/migrations/0046_document_events.py` depends on `("entities", "0021_event")`. It creates `corpus.DocumentEventRelation` (a foreign key to `entities.Event`) and `Document.events`. Because of this, `migrate` fails on a fresh install without `entities`.
    -   **Models:** `Document.index_data`, `Document.prep_index_chunk` and `Document.merge_with` refer directly to person, place and event relations.
    -   **Admin:** `DocumentAdmin` includes the Person, Place and Event inlines.
    -   **Metadata export, views and templates:** these include people and places columns, related entities on the document detail page, and links to entity admin pages and the People/Places pages.
    -   **Tests:** some corpus tests use entity models and fixtures.

An initial triage (commit `61a2f0ef`) commented out the entity code in `corpus`. That showed the scope of the problem, but it also broke things:

-   Indexing raised a `NameError`, because `places` was still used after its definition was commented out.
-   Merging documents silently lost person and place links, because they cascade-delete with the merged document.

### Constraints

-   **No data loss in existing databases.** Existing table names (`db_table`) are kept. No tables or columns are dropped.
-   Migrations that have already been applied are not changed, with one deliberate exception (`corpus/0046`, see below).
-   The existing code style is followed.

## Decision

Dependencies go in one direction only: **`entities` → `corpus`, never `corpus` → `entities`**. This applies to Python imports, migrations, templates and tests.

`corpus` defines generic extension points. `entities` registers its behaviour into them when it is installed.

### 1. Move `DocumentEventRelation` into `entities`

-   The `DocumentEventRelation` model moves to `geniza/entities/models.py`. It keeps `Meta.db_table = "corpus_documenteventrelation"`, so the existing table and data are reused.
-   The relation is declared from the `entities` side as `Event.documents`, a many-to-many field through `DocumentEventRelation` with `related_name="events"`. Because of this, `document.events` and `document.documenteventrelation_set` still work.
-   **Migrations:**
    -   `corpus/0046_document_events.py` becomes a no-op (`operations = []`) that depends only on `corpus.0045`. This is the one deliberate edit to an applied migration. It's needed because otherwise `corpus` can never migrate without `entities`.
    -   `entities/0022_event_permissions.py` no longer references the `documenteventrelation` permission codenames. On a fresh install, that model doesn't exist yet at that point in the migrations.
    -   A new migration, `entities/0037_documenteventrelation.py`:
        -   creates the table only if it doesn't exist yet (`CreateModelIfMissing`). Rolling back never drops the table.
        -   adds `Event.documents`;
        -   moves the `ContentType` row from `corpus` to `entities`;
        -   assigns the four `documenteventrelation` permissions to the "Content Editor" and "Content Admin" groups.

### 2. Extension hooks on `Document`

`Document` gets these class attributes:

| Attribute          | Type                                         | Used by                                |
| ------------------ | -------------------------------------------- | -------------------------------------- |
| `extra_prefetches` | list of prefetch names or `Prefetch` objects | `prep_index_chunk`                     |
| `index_data_hooks` | list of callables `(doc) -> dict`            | `index_data`, which merges the results |
| `merge_hooks`      | list of callables `(primary, merged)`        | `merge_with`                           |

The hard-coded entity prefetches, index fields (`people_count_i`, `places_count_i`, `places_ids_ss`) and entity merge calls are removed from `corpus`. `_merge_entities` stays on `Document` so that the hooks can reuse it.

The entity implementations are in `geniza/entities/hooks.py`:

-   `document_entity_index_data(doc)`
-   `merge_document_entities(primary, merged)`. This merges person, place and event relations, so the person/place merging that the triage broke works again.

They are registered in `EntitiesConfig.ready()` (`geniza/entities/apps.py`).

### 3. Admin

-   `DocumentEventInline`, and `DocumentEventWidgetWrapper` if only the event inline uses it, move from `corpus` to `entities/admin.py`.
-   `entities/admin.py` adds the Person, Place and Event inlines to `DocumentAdmin`. It does this either by appending to `DocumentAdmin.inlines` or by re-registering a subclass of `DocumentAdmin`.
-   The commented-out entity code is removed from `corpus/admin.py`.

### 4. Metadata export, views and templates

-   `DocumentExporter` gets `extra_prefetches`, `extra_field_hooks` and `export_data_hooks`. The entity hooks live in `entities/hooks.py`. Place columns go after the base document fields.
-   The `export_metadata` command adds the people and places exporters only when `apps.is_installed("geniza.entities")` is true. The output paths are derived from the configured exporters.
-   `DocumentDetailView` adds `related_people` and `related_places` only when `entities` is installed.
-   A new context variable, `entities_enabled`, is added in `geniza.context_processors.template_globals`. Templates use it to wrap entity-specific content, for example in `corpus/snippets/document_option_label.html` and in the People/Places menu links in `templates/snippets/menu.html`.

### 5. Tests and CI guard

-   Corpus tests that need entities move to `geniza/entities/tests/` (for example `test_entities_documents.py`).
-   `geniza/conftest.py` and `geniza/urls.py` include entity fixtures and URLs only when `entities` is installed.
-   In `unit_tests.yml`, the tests run as a matrix with two jobs: `full` and `corpus only`. The `corpus only` job:
    -   adds `INSTALLED_APPS.remove("geniza.entities")` to the generated `local_settings.py` (no separate settings module is needed);
    -   runs a static check: `grep -rn "geniza.entities\|\"entities\." geniza/corpus`, outside `tests/`, must return nothing;
    -   runs pytest, which migrates a fresh database;
    -   runs `makemigrations --check` on pull requests.

## Consequences

### Positive

-   `geniza.corpus` installs, migrates and passes its tests without `geniza.entities`.
-   CI enforces the one-way dependency, so new `corpus` → `entities` references are caught.
-   Merging documents keeps person and place links again, and indexing works again.
-   Existing data and table names don't change.

### Negative and risks

-   An applied migration (`corpus/0046`) and an earlier `entities` migration (`0022`) were edited. Existing databases work fine, because the new `entities/0037` migration is idempotent about the table. Still, this departs from normal Django practice.
-   The `DocumentEventRelation` table keeps a `corpus_` prefix even though it belongs to `entities`. This can be confusing.
-   Some behaviour now happens through hooks registered in `AppConfig.ready()`. This is less explicit than direct code: to understand indexing, merging, the admin or exports, you now have to look in both apps.
-   Hook registration is global class state. Tests that change the hooks need to restore them.

### Known issues (not caused by this change)

-   `sqlmigrate entities 0037` fails with `NodeNotFoundError` for `djiffy.0003_extra_data_revisions`. djiffy now ships a squashed migration, and `sqlmigrate` doesn't apply replacements. `migrate` works.
-   The failures in `test_language_switcher` and `test_output_message_logger` were already there before this change.

## Deployment

Before deploying to production:

1. Make a backup with `pg_dump -Fc`.
2. Run the migrations against a copy of production.
3. Check that `select count(*) from corpus_documenteventrelation` gives the same result before and after.
4. Check that the `ContentType` for `documenteventrelation` now has `app_label = 'entities'`.
5. Check that the migration SQL contains no `DROP` statements.

## Verification

These checks were done for step 1:

-   `makemigrations --check --dry-run` reports no changes.
-   On a copy of the local database, `entities.0037` was applied. The row count stayed the same (23), the content type moved to `entities`, and the permissions were assigned to both groups. Rolling back to `0036` and re-applying kept all the rows.
-   On an empty database, a full `migrate` succeeded.

Current test results:

| Configuration | Passed | Failed           |
| ------------- | ------ | ---------------- |
| Corpus only   | 647    | 2 (pre-existing) |
| Full          | 824    | 2 (pre-existing) |
