from geniza.settings.components.base import BASE_DIR, WEBPACK_LOADER

# Development webpack config: use the dev stats file to load bundles into
# memory, and don't cache anything
WEBPACK_LOADER["DEFAULT"].update(
    {
        "CACHE": False,
        # FIXME why is .parent required here? BASE_DIR should be project root
        "STATS_FILE": BASE_DIR.parent / "sitemedia" / "webpack-stats-dev.json",
    }
)
