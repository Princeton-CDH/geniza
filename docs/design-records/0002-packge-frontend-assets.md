# Make geniza frontend sources available to dependent projects

-   Status: Proposed
-   Deciders: @rlskoeser, ...? [TBD]
-   Date: 2026-11-13

Related: [0001 Make `geniza.corpus` usable without `geniza.entities`](0001-entities-optional-for-corpus.md)

## Context

The `madad` project installs `geniza` as a Python dependency (via `uv`, from git) to reuse its Django apps, models and templates. Madad will also need to reuse and adapt geniza frontend code: SCSS, Stimulus controllers, IIIF/transcription viewer JavaScript, and webpack bundle names referenced by geniza templates (`{% render_bundle "main" %}`, `"iiif"`, etc.).

In the current version of the `geniza` codebase this is not possible without a separate checkout of the repository:

-   All frontend sources live in `sitemedia/` at the repository root, outside the `geniza` Python package, so they are not included when geniza is installed as a package.
-   Compiled bundles (`sitemedia/bundles/`) and `sitemedia/webpack-stats.json` are gitignored, so a git-based install cannot provide prebuilt assets either.
-   `webpack.config.js` resolves entries and output relative to its own directory (`__dirname`), so it cannot be reused as-is from another project.
-   `pyproject.toml` declares `packages = ["geniza"]` with setuptools, which lists only the top-level package; subpackages are not included in a regular (non-editable) wheel build without package discovery.

### Constraints

1. **No change to PGP behavior**: the PGP site must build, test and deploy as before; existing CI (`npm ci`, `npm run build`, `webpack-stats-ci.json` copy) and deploy scripts must keep working or be updated in the same change.
2. Madad must be able to build its frontend from an installed `geniza` package, **without requiring a sibling checkout** of the geniza repository.
3. **Installing geniza as a Python package must not require Node.js**.
4. Madad must be able to customize and extend styles and scripts, not just consume geniza's compiled output.

## Options considered

### A. Git submodule or editable install of geniza in madad

Madad adds geniza as a git submodule (or `uv` editable path dependency) and points its webpack config at the checkout.

-   ➕ No changes needed in geniza.
-   ➖ Submodules add workflow friction; editable path installs only work on machines with a sibling checkout (violates constraint 2 for CI/deploy).
-   ➖ Python package version and frontend source version can drift apart.

### B. Copy compiled bundles from a geniza build into madad

-   ➕ Quickest to get running.
-   ➖ No customization possible (violates constraint 4); copies go stale; production `publicPath` is hard-coded to `/static/bundles/`.

### C. Include `sitemedia/` in the package via setuptools `package-dir` mapping

Map the root `sitemedia/` directory into the package as `geniza/sitemedia` at build time.

-   ➕ No files move; PGP unaffected.
-   ➖ Relies on treating a non-Python directory as a package (`package-dir` + `package-data`); works but is non-obvious and may produce warnings.

### D. Move `sitemedia/` into the `geniza` package

`git mv sitemedia geniza/sitemedia` and update references.

-   ➕ Conventional layout; works with any build backend.
-   ➖ Touches webpack config, settings (`STATICFILES_DIRS`, `WEBPACK_LOADER`), `.gitignore`, CI workflow, and deploy scripts; large diff and risk of missed references.

### E. Switch build backend to hatchling and use `force-include`

Replace setuptools with hatchling and map `sitemedia/` into the wheel as `geniza/sitemedia`, without moving files.

-   ➕ No files move; PGP layout, webpack config, CI and deploy unchanged.
-   ➕ `force-include` is a supported, documented feature for exactly this case.
-   ➕ `packages = ["geniza"]` includes subpackages automatically, fixing the existing subpackage gap.
-   ➕ Optional `artifacts` setting allows shipping prebuilt bundles in a wheel built by CI, if ever needed.
-   ➖ Changes the build backend; packaging config must be re-verified (version, readme, package data such as templates, locale, fixtures and migrations).

### F. Switch build backend to `uv_build`

-   ➕ Simple and fast.
-   ➖ Designed for pure-Python packages with a fixed layout; would require option D as well, and has limited support for mapping external directories or build hooks. To be confirmed against current uv documentation.

### Comparison

|                                  | C. setuptools         | D. move                               | E. hatchling          | F. uv_build     |
| -------------------------------- | --------------------- | ------------------------------------- | --------------------- | --------------- |
| Keep `sitemedia/` at root        | hacky (`package-dir`) | no                                    | yes (`force-include`) | no (needs D)    |
| Subpackages included             | needs `packages.find` | needs `packages.find` (if setuptools) | automatic             | automatic       |
| Ship prebuilt bundles (optional) | explicit package-data | backend-dependent                     | `artifacts`           | to be confirmed |
| Run npm during build (optional)  | custom command        | backend-dependent                     | build hook            | not supported   |
| Changes to PGP webpack/CI/deploy | none                  | many                                  | none                  | many            |

## Proposed solution

**Option E**: switch geniza's build backend to hatchling and include the root `sitemedia/` sources in the wheel as `geniza/sitemedia`. Madad runs its own webpack build against the installed sources.

1. Geniza packaging (`pyproject.toml`):

    ```toml
    [build-system]
    requires = ["hatchling"]
    build-backend = "hatchling.build"

    [project]
    dynamic = ["version"]

    [tool.hatch.version]
    path = "geniza/__init__.py"   # replaces setuptools dynamic attr = geniza.__version__

    [tool.hatch.build.targets.wheel]
    packages = ["geniza"]

    [tool.hatch.build.targets.wheel.force-include]
    "sitemedia" = "geniza/sitemedia"
    ```

    Gitignored build output (`sitemedia/bundles/`, `webpack-stats.json`) is excluded by default; geniza ships **sources only**. `package.json` and `package-lock.json` should also be included (e.g. force-included as `geniza/sitemedia/package.json` or alongside) so madad can align its JS dependency versions.

2. Madad locates the sources from the installed package:

    ```python
    import geniza, pathlib
    GENIZA_SITEMEDIA = pathlib.Path(geniza.__path__[0]) / "sitemedia"
    ```

    The madad npm scripts pass this path to webpack (e.g. via an environment variable set by `python -c ...`), and madad's `webpack.config.js` uses it for geniza entry points, a `@geniza` resolve alias, and Sass load paths (Sass `webpackImporter` is disabled, so aliases need a matching `loadPaths`/`includePaths` entry).

3. Madad owns its `package.json`, `webpack.config.js`, `WEBPACK_LOADER` and `STATICFILES_DIRS` settings, and builds its own bundles using the same entry names geniza templates expect.

4. Optional follow-up (not part of this decision): refactor geniza's `webpack.config.js` to export a configurable factory (base directory, entries) so madad can reuse loaders/plugins instead of duplicating them.

## Results

### Positive Consequences

-   Madad can build and customize frontend assets from a normal package install, in CI and deploys, with no sibling checkout.
-   PGP repository layout, webpack config, CI and deploy are unchanged.
-   Fixes the latent subpackage omission in non-editable wheel builds.
-   Frontend sources are versioned together with the Python code madad depends on.

### Negative Consequences

-   Build backend change requires re-verifying package contents (templates, locale files, migrations, fixtures, static data).
-   JS dependency versions must be kept aligned between geniza and madad `package.json` files.
-   Madad needs Node.js for its own build (but installing geniza does not).

## Verification

-   `uv build` in geniza produces a wheel containing `geniza/sitemedia/{js,scss,img,...}` and all subpackages, templates, locale files and migrations; compare wheel contents before and after the change.
-   PGP CI (unit tests, `npm run build`) passes unchanged.
-   In madad, `uv sync` from git followed by `npm run build` succeeds without a geniza checkout, and pages using `{% render_bundle %}` render with madad's bundles.
