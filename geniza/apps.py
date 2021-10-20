from django.contrib.admin.apps import AdminConfig
from django.contrib.staticfiles.apps import StaticFilesConfig


class GenizaAdminConfig(AdminConfig):
    default_site = "geniza.admin.GenizaAdminSite"


class GenizaStaticFilesConfig(StaticFilesConfig):
    # don't collect frontend source files when running collectstatic
    ignore_patterns = StaticFilesConfig.ignore_patterns + ["*.esm.js", "*.scss"]
