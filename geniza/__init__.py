__version_info__ = (4, 17, 1, None)


# Dot-connect all but the last. Last is dash-connected if not None.
__version__ = ".".join([str(i) for i in __version_info__[:-1]])
if __version_info__[-1] is not None:
    __version__ += "-%s" % (__version_info__[-1],)


# context processor to add version to the template environment
def context_extras(request):
    return {
        # software version
        "SW_VERSION": __version__
    }
