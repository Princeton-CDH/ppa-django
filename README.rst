ppa-django
==============

.. sphinx-start-marker-do-not-remove

Django web application for the new `Princeton Prosody Archive
<https://cdh.princeton.edu/princeton-prosody-archive/>`_.

Code and architecture documentation for the current release available
at `<https://princeton-cdh.github.io/ppa-django/>`_.

.. image:: https://travis-ci.org/Princeton-CDH/ppa-django.svg?branch=master
   :target: https://travis-ci.org/Princeton-CDH/ppa-django
   :alt: Build status

.. image:: https://landscape.io/github/Princeton-CDH/ppa-django/master/landscape.svg?style=flat
   :target: https://landscape.io/github/Princeton-CDH/ppa-django/master
   :alt: Code Health

.. image:: https://codecov.io/gh/Princeton-CDH/ppa-django/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/Princeton-CDH/ppa-django
   :alt: Code coverage

.. image:: https://requires.io/github/Princeton-CDH/ppa-django/requirements.svg?branch=master
   :target: https://requires.io/github/Princeton-CDH/ppa-django/requirements/?branch=master
   :alt: Requirements Status

This repo uses `git-flow <https://github.com/nvie/gitflow>`_ conventions; **master**
contains the most recent release, and work in progress will be on the **develop** branch.
Pull requests should be made against develop.


Development instructions
------------------------

Initial setup and installation:

- **recommended:** create and activate a python 3.5 virtualenv::

     virtualenv ppa -p python3.5
     source ppa/bin/activate

- Use pip to install required python dependencies::

    pip install -r requirements.txt
    pip install -r dev-requirements.txt

- Copy sample local settings and configure for your environment::

   cp ppa/local_settings.py.sample ppa/local_settings.py

- Create a database, configure in local settings, and run migrations::

    python manage.py migrate

- Create two new Solr cores with a basic configuration and managed schema,
  using the core/collection names for development and testing that you
  configured in local settings::

    solr create -c SOLR_CORE -n basic_configs
    solr create -c SOLR_TEST_CORE -n basic_configs

- Run the manage command to configure the schema::

    python manage.py solr_schema

  The manage command will automatically reload the core to ensure schema
  changes take effect.

- Bulk import (*provisional*): requires a local copy of HathiTrust data as
  pairtree provided by rsync.  Configure the path in `localsettings.py`
  and then run::

    python manage.py hathi_import

- Then index the imported content into Solr:

    python manage.py index

Frontend development setup:

- django-compressor dependencies: you need `Node.js <https://nodejs.org/en/>`_
  and a js package manager (`npm` or `yarn`). Install dependencies with the
  relevant install command for your package manager - for `npm`::

    npm install

  for `yarn`::

    yarn

  if you wish to install dependencies globally, take a look at the optional
  settings for `django-compressor-toolkit <https://github.com/kottenator/django-compressor-toolkit>`_.


Unit Tests
~~~~~~~~~~

Unit tests are written with `py.test <http://doc.pytest.org/>`_ but use
Django fixture loading and convenience testing methods when that makes
things easier. To run them, first install development requirements::

    pip install -r dev-requirements.txt

Run tests using py.test::

    py.test

Make sure you configure a test solr connection and set up an empty
Solr core using the same instructions as for the development core.


Documentation
-------------

Documentation is generated using `sphinx <http://www.sphinx-doc.org/>`__
To generate documentation them, first install development requirements::

    pip install -r dev-requirements.txt

Then build documentation using the customized make file in the `docs`
directory::

    cd sphinx-docs
    make html

When building for a release ``make docs`` will create a folder called ``docs``,
build the HTML documents and static assets, and force add it to the commit for
use with Github Pages.

License
-------
This project is licensed under the `Apache 2.0 License <https://github.com/Princeton-CDH/ppa-django/blob/master/LICENSE>`_.
