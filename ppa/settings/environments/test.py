from ppa.settings import DATABASES, SOLR_CONNECTIONS

# These settings correspond to the service container settings in the
# .github/workflow .yml files.
DATABASES["default"].update(
    {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "ppa",
        "PASSWORD": "ppa",
        "USER": "ppa",
        "HOST": "127.0.0.1",
        "PORT": "5432",
        "TEST": {
            "CHARSET": "utf8",
        },
    }
)

SOLR_CONNECTIONS["default"].update(
    {
        "URL": "http://localhost:8983/solr/",
        "COLLECTION": "ppa",
        "CONFIGSET": "ppa",
        # set aggressive commitWithin for test
        "COMMITWITHIN": 750,
        "TEST": {"COMMITWITHIN": 100},
    }
)

# turn off debug so we see 404s when testing
DEBUG = False

# required for tests when DEBUG = False
ALLOWED_HOSTS = ["*"]

# use a fake webpack loader to ignore missing assets for unit tests
WEBPACK_LOADER = {
    "DEFAULT": {"LOADER_CLASS": "webpack_loader.loaders.FakeWebpackLoader"}
}
