from ppa.settings import CSP_SCRIPT_SRC, CSP_STYLE_SRC, CSP_CONNECT_SRC


DEBUG = True

# ALLOWED_HOSTS = ["*"]
CSP_REPORT_ONLY = True

if DEBUG:
    # allow webpack dev server through CSP when in DEBUG
    CSP_SCRIPT_SRC += ("http://localhost:3000", "'unsafe-eval'", "'unsafe-inline'")
    CSP_STYLE_SRC += ("http://localhost:3000", "'unsafe-inline'")
    CSP_CONNECT_SRC += (
        "http://localhost:3000",
        "ws://localhost:3000",
    )
