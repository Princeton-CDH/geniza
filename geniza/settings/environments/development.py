# if in debug mode, allow webpack dev server through CSP controls
if DEBUG:
    CSP_CONNECT_SRC = ("ws://localhost:3000",)
