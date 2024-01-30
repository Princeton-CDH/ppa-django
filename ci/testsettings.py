# This file is exec'd from settings.py, so it has access to and can
# modify all the variables in settings.py.

# If this file is changed in development, the development server will
# have to be manually restarted because changes will not be noticed
# immediately.

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "ppa",
        "PASSWORD": "ppa",
        "USER": "ppa",
        "HOST": "127.0.0.1",
        "PORT": "5432",
        "TEST": {
            "CHARSET": "utf8",
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

# use a fake webpack loader to ignore missing assets for unit tests
WEBPACK_LOADER = {
    "DEFAULT": {"LOADER_CLASS": "webpack_loader.loaders.FakeWebpackLoader"}
}

# secret key added as a travis build step
