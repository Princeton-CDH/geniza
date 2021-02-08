# if django-debug-toolbar is installed, enable it

from geniza.settings.components.base import INSTALLED_APPS, MIDDLEWARE

INTERNAL_IPS = [
    '127.0.0.1',
]

try:
    import debug_toolbar
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE += (
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    )
except ImportError:
    pass
