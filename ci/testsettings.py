# This file is exec'd from settings.py, so it has access to and can
# modify all the variables in settings.py.

# If this file is changed in development, the development server will
# have to be manually restarted because changes will not be noticed
# immediately.

DEBUG = False

# include database settings to use Mariadb ver on production (5.5)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'test',
        'USER': 'root',
        'HOST': 'localhost',
        'PORT': '',
        'TEST': {
            'CHARSET': 'utf8',
            'COLLATION': 'utf8_general_ci',
        },
    },
}


# required by mezzanine for unit tests
ALLOWED_HOSTS = ['*']

# required for integration tests that query Solr
SOLR_CONNECTIONS = {
    'default': {
        'URL': 'http://localhost:8983/solr/',
        'COLLECTION': 'ppa-pa11y',
        'CONFIGSET': 'ppa',
        'TEST': {
            'COLLECTION': 'test-ppa',
            'COMMITWITHIN': 100
        }
    }
}

# secret key added as a travis build step
