from split_settings.tools import optional, include

include(
    'components/base.py',
#    'components/database.py',
    # optional('local_settings.py')
    'local_settings.py'
)