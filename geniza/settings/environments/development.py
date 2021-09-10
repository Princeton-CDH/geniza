# if in debug mode, allow webpack dev server and django debug toolbar thru CSP
if DEBUG:
    CSP_SCRIPT_SRC = ("http://localhost:8000",)
    CSP_CONNECT_SRC = ("ws://localhost:3000",)
