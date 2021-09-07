# if in debug mode, allow webpack dev server through CSP controls
if DEBUG:
    CSP_SCRIPT_SRC += ("http://localhost:3000", "'unsafe-eval'", "'unsafe-inline'")
    CSP_STYLE_SRC += ("http://localhost:3000", "'unsafe-inline'")
    CSP_CONNECT_SRC += (
        "http://localhost:3000",
        "ws://localhost:3000",
    )
