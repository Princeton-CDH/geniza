from django.core.management.commands import makemessages

from geniza import __version__

class Command(makemessages.Command):
    """Custom version of makemessages that sets more options for xgettext."""
    # For invocation options for xgettext, see:
    # https://www.gnu.org/software/gettext/manual/html_node/xgettext-Invocation.html

    xgettext_options = makemessages.Command.xgettext_options + [
        "--copyright-holder=The Trustees of Princeton University"
        "--msgid-bugs-address=cdhdevteam@princeton.edu"
        f"--package-version={__version__}",
        "--package-name=geniza",
    ]
