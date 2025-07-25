"""
Django settings for ppa project.
"""

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# called from ppa-django/ppa/settings/__init__.py
# do NOT import this module directly, the path will be different
PROJECT_APP_PATH = Path(__file__).resolve().parent.parent
PROJECT_APP = PROJECT_APP_PATH.name
# base dir is one level up from that (ppa-django)
BASE_DIR = PROJECT_APP_PATH.parent

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = []

# Every cache key will get prefixed with this value - here we set it to
# the name of the directory the project is in to try and use something
# project specific.
CACHE_MIDDLEWARE_KEY_PREFIX = PROJECT_APP

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = "/static/"

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = BASE_DIR / STATIC_URL.strip("/")

# Additional locations of static files
STATICFILES_DIRS = [
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    BASE_DIR / "sitemedia",
    BASE_DIR / "bundles",
]

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = "/media/"

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = BASE_DIR / MEDIA_URL.strip("/")

STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)

# Application definition

INSTALLED_APPS = [
    "ppa.apps.LocalAdminConfig",  # replaces 'django.contrib.admin'
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.humanize",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sites",
    "django.contrib.staticfiles",
    "django.contrib.redirects",
    "django.contrib.sitemaps",
    "django_cas_ng",
    "pucas",
    "semanticuiforms",
    "webpack_loader",
    # 'wagtail.contrib.forms',
    "wagtail.contrib.legacy.richtext",
    "wagtail.contrib.redirects",
    "wagtail.contrib.settings",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.embeds",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
    "fullurl",
    "admin_log_entries",
    "import_export",
    "parasolr",
    "ppa.archive",
    "ppa.common",
    "ppa.pages",
    "ppa.editorial",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.legacy.sitemiddleware.SiteMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
    "csp.middleware.CSPMiddleware",
]

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "django_cas_ng.backends.CASBackend",
)

ROOT_URLCONF = "ppa.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "ppa.context_extras",
                "ppa.context_processors.template_globals",
                "wagtail.contrib.settings.context_processors.settings",
            ],
            "loaders": [
                "apptemplates.Loader",
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
        },
    },
]

WSGI_APPLICATION = "ppa.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "ppa",
        "USER": "ppa",
        "PASSWORD": "",
        "HOST": "",  # empty string for localhost
        "PORT": "",  # empty string for default
    }
}

SOLR_CONNECTIONS = {
    "default": {
        "URL": "http://localhost:8983/solr/",
        "COLLECTION": "ppa",
        "CONFIGSET": "ppa",
        "TEST": {
            # set aggressive commitWithin when testing
            "COMMITWITHIN": 750,
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Password validation
# https://docs.djangoproject.com/en/1.11/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/

LANGUAGE_CODE = "en-us"

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
TIME_ZONE = "America/New_York"

USE_I18N = True

USE_TZ = True

SITE_ID = 1

WAGTAIL_SITE_NAME = "Princeton Prosody Archive"
# needed by wagtail to generate URLs for notification emails
WAGTAILADMIN_BASE_URL = "https://prosody.princeton.edu/"

WAGTAILEMBEDS_FINDERS = [
    {"class": "wagtail.embeds.finders.oembed"},
    {"class": "ppa.pages.embed_finders.GlitchEmbedFinder"},
]

# username for logging activity by local scripts
SCRIPT_USERNAME = "script"

# PUCAS configuration for CAS/LDAP login and user provisioning.
# Only includes non-sensitive configurations that do not change
PUCAS_LDAP = {
    # basic user profile attributes
    "ATTRIBUTES": ["givenName", "sn", "mail"],
    "ATTRIBUTE_MAP": {
        "first_name": "givenName",
        "last_name": "sn",
        "email": "mail",
    },
}

# Django webpack loader
WEBPACK_LOADER = {
    "DEFAULT": {
        "CACHE": True,
        "BUNDLE_DIR_NAME": "bundles/",  # must end with slash
        "STATS_FILE": BASE_DIR / "webpack-stats.json",
        "POLL_INTERVAL": 0.1,
        "TIMEOUT": None,
        "IGNORE": [r".+\.hot-update.js", r".+\.map"],
    }
}

# defaults for HathiTrust dataset rsync, per their documentation
HATHITRUST_RSYNC_SERVER = "datasets.hathitrust.org"
HATHITRUST_RSYNC_PATH = ":ht_text_pd"

# django-csp configuration for content security policy definition and
# violation reporting - https://github.com/mozilla/django-csp

# fallback for all protocols: block it
CSP_DEFAULT_SRC = "'none'"

# allow loading js locally, from a cdn, and from google (for analytics)
CSP_SCRIPT_SRC = (
    "'self'",
    "https://cdnjs.cloudflare.com",
    "https://www.googletagmanager.com",
    "*.glitch.me",
    "localhost",
)

# allow loading fonts locally and from google (via data: url)
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com data:")

# allow loading css locally and from google (for fonts)
CSP_STYLE_SRC = ("'self'", "https://fonts.googleapis.com", "*.glitch.me")

# allow loading local images, hathi page images, google tracking pixel, gale images
CSP_IMG_SRC = (
    "'self'",
    "https://babel.hathitrust.org",
    "https://www.google-analytics.com",
    "https://callisto.ggsrv.com",  # old Gale image server
    "https://luna.gale.com",  # new Gale image server
)

# exclude admin and cms urls from csp directives since they're authenticated
CSP_EXCLUDE_URL_PREFIXES = ("/admin", "/cms")

# allow usage of nonce for inline js (for analytics)
CSP_INCLUDE_NONCE_IN = ("script-src",)

# allow local scripts to connect to source (i.e. searchLoading)
CSP_CONNECT_SRC = (
    "'self'",
    "https://www.google-analytics.com",
    "*.glitch.me",
    "fonts.googleapis.com",
)

# load a manifest file
CSP_MANIFEST_SRC = "'self'"
