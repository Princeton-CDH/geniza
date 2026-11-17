# Make `geniza.corpus` usable without `geniza.entities`

-   Status: Draft Implementation
-   Author: @rlskoeser;
    -   Supported by: OpenCode:claude-opus-5.5
-   Reviewers: @laurejt
-   Approvers: @rlskoeser, ...? [TBD]
-   Date: 2026-11-12

Related issues and pull requests:

-   [madad#1](https://github.com/Princeton-CDH/madad/issues/1)
-   PR: [geniza#2041](https://github.com/Princeton-CDH/geniza/pull/2041)

## Context

We have hoped and suggested that the `geniza` codebase that powers [PGPv4](https://geniza.princeton.edu/) could be reused for other projects. We now have an in-house use-case for that with the [Madad](https://cdh.princeton.edu/projects/madad/) project, which has overlapping functionality with PGP. We want to make it easier for othre projects to reuse and adapt the existing codebase, and to use part of the application without needing to use all of it. In particular, the Madad project plans to use and extend Documents, Fragments, and related models included in the `geniza.corpus` corpus but does not plan to include Person/Place data. We want to install the `geniza.corpus` without installing the `geniza.entities` app.

This is not possible in the current version of the `geniza` codebase (as of 4.33-dev); the `corpus` and `entities` apps have circular dependencies and mixed imports. (See [Current State](#current-state) for more details.)

### Constraints

1. **No data loss** is acceptable in the production PGPv4 application. Any changes made must preserve existing database content.
2. The existing ansible deploy should automatically apply django migrations without manual intervention when this update is deployed to staging and production PGP environments.
3. No user-facing functionality changes: PGPv4 should work as it did prior to the refactor.

### Proposed solution

For `entities` to be optional, dependencies (→) must go in one direction: **`entities` → `corpus`, never `corpus` → `entities`**. This applies to Python imports, migrations, templates and unit tests.

`corpus` defines generic extension points; `entities` registers behavior when the app is installed.

1. Refactor code to make dependencies one-directional, with no circular imports. `entities` depends on `corpus`, but `corpus` should be written and tested so that it can be used without `entities`.
    - Move all entity-specific code out of `corpus` and into `entities`
    - Add hooks where necessary in the `corpus` code so that entity-specific integrations are enabled when the `entities` application is installed.
2. For constraint 1: the simplest solution is to preserve existing table names (`db_table`) in the current location as entity-specific models are moved from `corpus` to `entities`. No tables or columns will be removed.
3. For constraint 2: Django migrations in the `corpus` and `entities` apps will be revised so they can be run independently and work on both an existing database and a fresh install.

## Results of the proposed solution

### Positive Consequences

-   `geniza.corpus` installs, migrates and unit tests pass without `geniza.entities` app included in Django installed apps.
-   Continuous integration and pre-commit hooks have checks to enforces the one-way dependency; changes introducing new `corpus` → `entities` references should be caught automatically.
-   Merging documents includes merging of person and place links; indexing works as before.
-   Existing data and table names don't change.
-   `geniza.corpus` can be used in other Django project without installing `geniza.entities` (tested in preliminary `madad` Django application).

### Negative Consequences

-   Existing migrations (`corpus.0046`, `entities.0022`) have been modified. This should work for both existing and new databases since the new `entities.0037` migration has been written to be idempotent about the table, but is unexpected behavior for Django migrations. It will be important to test carefully.
-   The `DocumentEventRelation` model overrides the database table name to preserve the existing `corpus_` prefix even though it has been moved into the `entities` app. This is potentially confusing in the long run, especially for new installations, since it violates Django default naming conventions (database table name prefix corresponds to app name).
    -   This may be worth an additional migration to drop the override and rename the existing table.
-   Some behavior now happens through hooks registered in `AppConfig.ready()`. This is less explicit than direct code: understanding the logic for indexing, merging, the admin or exports requires looking in both apps.
-   Hook registration is global class state. Tests that change the hooks need to restore them.

## Details

### Current state {#current-state}

Currently the `entities` and `corpus` apps depend on each other:

-   `entities` depends on `corpus`: `entities.models` imports `Document`, `Dating`, `LanguageScript`, `PermalinkMixin` and `DisplayLabelMixin` from `corpus.models`
-   `corpus` depends on `entities`, in several places:
    -   **Migrations:** `corpus/migrations/0046_document_events.py` depends on `("entities", "0021_event")`. It creates `corpus.DocumentEventRelation` (a foreign key to `entities.Event`) and `Document.events`. Because of this dependency, `migrate` fails on a fresh install without the `entities` app installed.
    -   **Models:** `Document.index_data`, `Document.prep_index_chunk` and `Document.merge_with` refer directly to person, place and event relations.
    -   **Admin:** `DocumentAdmin` includes the Person, Place and Event inlines.
    -   **Metadata export, views and templates:** these include people and places columns, related entities on the document detail page, and links to entity admin pages and the People/Places pages.
    -   **Tests:** some corpus tests use entity models and fixtures.

### Changes

#### 1. Move `DocumentEventRelation` into `entities`

-   The `DocumentEventRelation` model moves to `geniza/entities/models.py`. It sets a `Meta.db_table = "corpus_documenteventrelation"` so that the existing table name will be used; no data movement.
-   The relation is declared from the `entities` side as `Event.documents`, a many-to-many field through `DocumentEventRelation` with `related_name="events"`. Because of this, `document.events` and `document.documenteventrelation_set` still work.
-   **Migrations:**
    -   `corpus/0046_document_events.py` is replaced with a no-op (`operations = []`) that depends only on `corpus.0045`, but drops the dependencies on `entities` migrations. This migration is preserved because it has already been applied in production to PGP.
    -   `entities/0022_event_permissions.py` no longer references the `documenteventrelation` permission codenames. On a fresh install, that model doesn't exist yet at that point in the migrations.
    -   A new migration, `entities/0037_documenteventrelation.py`:
        -   creates the table only if it doesn't exist yet (`CreateModelIfMissing`). Rolling back never drops the table.
        -   adds `Event.documents`;
        -   moves built-in Django `ContentType` entry from `corpus` to `entities`;
        -   assigns the four `documenteventrelation` permissions to the "Content Editor" and "Content Admin" groups.

#### 2. Extension hooks on `Document`

`Document` gets these class attributes:

| Attribute          | Type                                         | Used by                                |
| ------------------ | -------------------------------------------- | -------------------------------------- |
| `extra_prefetches` | list of prefetch names or `Prefetch` objects | `prep_index_chunk`                     |
| `index_data_hooks` | list of callables `(doc) -> dict`            | `index_data`, which merges the results |
| `merge_hooks`      | list of callables `(primary, merged)`        | `merge_with`                           |

The hard-coded entity prefetches, index fields (`people_count_i`, `places_count_i`, `places_ids_ss`) and entity merge calls are removed from `corpus`. `_merge_entities` stays on `Document` so that the hooks can reuse it.

The entity implementations are in `geniza/entities/hooks.py`:

-   `document_entity_index_data(doc)`
-   `merge_document_entities(primary, merged)`. This merges person, place and event relations, so the previous person/place merging functionality works unchanged.

They are registered in `EntitiesConfig.ready()` (`geniza/entities/apps.py`).

#### 3. Admin

-   `DocumentEventInline` and `DocumentEventWidgetWrapper` move from `corpus.admin` to `entities.admin`.
-   `entities.admin` adds Person, Place and Event inlines to `DocumentAdmin`. It does this either by appending to `DocumentAdmin.inlines` or by re-registering a subclass of `DocumentAdmin`.

#### 4. Metadata export, views and templates

-   `DocumentExporter` gets `extra_prefetches`, `extra_field_hooks` and `export_data_hooks`. The entity hooks live in `entities/hooks.py`. Place columns after the base document fields.
-   The `export_metadata` command adds the people and places exporters only when `apps.is_installed("geniza.entities")` is true. The output paths are derived from the configured exporters.
-   `DocumentDetailView` adds `related_people` and `related_places` only when `entities` is installed.
-   A new context variable, `entities_enabled`, is added in `geniza.context_processors.template_globals`. Templates use it to wrap entity-specific content, for example in `corpus/snippets/document_option_label.html` and in the People/Places menu links in `templates/snippets/menu.html`.

#### 5. Tests, CI, and pre-commit hook

-   Corpus tests that depend on entities move to `geniza/entities/tests/` (for example `test_entities_documents.py`).
-   `geniza/conftest.py` and `geniza/urls.py` include entity fixtures and URLs only when `entities` app is installed.
-   In `unit_tests.yml`, the tests run as a matrix in two modes: `full` (all geniza apps) and `corpus only` (without `entities`).
    -   Tests use the same local settings; the second mode uses `INSTALLED_APPS.remove("geniza.entities")` to adjust configuration.
-   A custom pre-commit hook has been added to prevent circular imports from being reintroduced in the future.

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
