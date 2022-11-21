# This file is exec'd from settings.py, so it has access to and can
# modify all the variables in settings.py.

# If this file is changed in development, the development server will
# have to be manually restarted because changes will not be noticed
# immediately.
import os

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "ppa",
        "PASSWORD": "ppa",
        "USER": "root",
        "HOST": "127.0.0.1",
        # "PORT": "3306",
        "OPTIONS": {
            # In each case, we want strict mode on to catch truncation issues
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        "TEST": {
            "CHARSET": "utf8",
            # "COLLATION": "utf8_general_ci",
        },
    },
}

# required by mezzanine for unit tests
ALLOWED_HOSTS = ["*"]

# required for integration tests that query Solr
SOLR_CONNECTIONS = {
    "default": {
        "URL": "http://localhost:8983/solr/",
        "COLLECTION": "ppa",
        "CONFIGSET": "ppa",
        "TEST": {"COMMITWITHIN": 100},
    }
}

# use an empty webpack-stats.json so we can ignore missing static files in tests
WEBPACK_LOADER = {
    "DEFAULT": {"STATS_FILE": os.path.join(BASE_DIR, "ci", "webpack-stats.json")}
}

# secret key added as a travis build step
