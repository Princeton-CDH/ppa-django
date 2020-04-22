ppa-django
==============

.. sphinx-start-marker-do-not-remove

Django web application for the new `Princeton Prosody Archive
<https://prosody.princeton.edu/>`_.

Code and architecture documentation for the current release available
at `<https://princeton-cdh.github.io/ppa-django/>`_.

.. image:: https://zenodo.org/badge/110731137.svg
   :target: https://doi.org/10.5281/zenodo.2400705
   :alt: DOI: 10.5281/zenodo.2400705

.. image:: https://travis-ci.org/Princeton-CDH/ppa-django.svg?branch=master
   :target: https://travis-ci.org/Princeton-CDH/ppa-django
   :alt: Build status

.. image:: https://codecov.io/gh/Princeton-CDH/ppa-django/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/Princeton-CDH/ppa-django
   :alt: Code coverage

.. image:: https://www.codefactor.io/repository/github/princeton-cdh/ppa-django/badge
   :target: https://www.codefactor.io/repository/github/princeton-cdh/ppa-django
   :alt: CodeFactor

.. image:: https://requires.io/github/Princeton-CDH/ppa-django/requirements.svg?branch=master
   :target: https://requires.io/github/Princeton-CDH/ppa-django/requirements/?branch=master
   :alt: Requirements Status

This repo uses `git-flow <https://github.com/nvie/gitflow>`_ conventions; **master**
contains the most recent release, and work in progress will be on the **develop** branch.
Pull requests should be made against develop.

Python 3.6 / Django 2.2 / Node 10.5.0 / MariaDB (MySQL) 5.5 w/ timezone info / Solr 6.6 (requires Java 8)

Development instructions
------------------------

Initial setup and installation:

- **recommended:** create and activate a python 3.6 virtual environment, perhaps with ``virtualenv`` or ``venv``

- Use pip to install required python dependencies::

   pip install -r requirements.txt
   pip install -r dev-requirements.txt

- Copy sample local settings and configure for your environment::

   cp ppa/local_settings.py.sample ppa/local_settings.py

- Create a database, configure in local settings in the `DATABASES` dictionary, change `SECRET_KEY`, and run migrations::

    python manage.py migrate

- Create two new Solr cores using project specific managed schema and
  solr config, using the core/collection names for development and
  testing that you configured in local settings::

    solr create -c ppa -d solr_conf
    solr create -c ppa-test -d solr_conf

- Run the manage command to configure the schema::

    python manage.py solr_schema

  The manage command will automatically reload the core to ensure schema
  changes take effect.

- Bulk import (*provisional*): requires a local copy of HathiTrust data as
  pairtree provided by rsync.  Configure the path in `localsettings.py`
  and then run::

    python manage.py hathi_import

- Then index the imported content into Solr::

    python manage.py index

Frontend development setup:

This project uses the `Semantic UI <https://semantic-ui.com/>`_ library in
addition to custom styles and javascript. You need to compile static assets
before running the server.

- To build all styles and js for production, including semantic UI::

    npm install
    npm run build

Alternatively, you can rebuild just the custom files or semantic independently.
This is useful if you make small changes and need to recompile once::

    npm run build:qa # just the custom files, with sourcemaps
    npm run build:prod # just the custom files, no sourcemaps
    npm run build:semantic # just semantic UI

Finally, you can run a development server with hot reload if you'll be changing
either set of assets frequently. These two processes are separate as well::

    npm run dev # serve just the custom files from memory, with hot reload
    npm run dev:semantic # serve just semantic UI files and recompile on changes

- If running this application on MariaDB/MySQL, you must make sure that
  time zone definitions are installed. On most flavors of Linux/MacOS,
  you may use the following command, which will prompt
  for the database server's root password::

    mysql_tzinfo_to_sql /usr/share/zoneinfo | mysql -u root mysql -p

  If this command does not work, make sure you have the command line utilities
  for MariaDB/MySQL installed and consult the documentation for your OS for
  timezone info. Windows users will need to install a copy of the zoneinfo
  files.

  See `MariaDB <https://mariadb.com/kb/en/library/mysql_tzinfo_to_sql/>`_'s
  info on the utility for more information.

Tests
~~~~~

Python unit tests are written with `py.test <http://doc.pytest.org/>`_ but use
Django fixture loading and convenience testing methods when that makes
things easier. To run them, first install development requirements::

    pip install -r dev-requirements.txt

Run tests using py.test.  Note that this currently requires the
top level project directory be included in your python path.  You can
accomplish this either by calling pytest via python::

    python -m pytest

Or, if you wish to use the ``pytest`` command directly, simply add the
top-level project directory to your python path environment variable::

  setenv PYTHONPATH .  # csh
  export PYTHONPATH=.  # bash

Make sure you configure a test solr connection and set up an empty
Solr core using the same instructions as for the development core.

Javascript unit tests are written with `Jasmine <https://jasmine.github.io/>`_
and run using `Karma <https://karma-runner.github.io/2.0/index.html>`_. To run
them, you can use an ``npm`` command::

    npm test

Automated accessibility testing is also possible using `pa11y <https://github.com/pa11y/pa11y>`_
and `pa11y-ci <https://github.com/pa11y/pa11y-ci>`_. To run accessibility tests,
start the server with ``python manage.py runserver`` and then use ``npm``::

    npm run pa11y

The accessibility tests are configured to read options from the ``.pa11yci.json``
file and look for a sitemap at ``localhost:8000/sitemap.xml`` to use to crawl the
site. Additional URLs to test can be added to the `urls` property of the
``.pa11yci.json`` file.


Documentation
-------------

Documentation is generated using `sphinx <http://www.sphinx-doc.org/>`__
To generate documentation them, first install development requirements::

    pip install -r dev-requirements.txt

Then build documentation using the customized make file in the ``docs``
directory::

    cd sphinx-docs
    make html

When building for a release ``make docs`` will create a folder called ``docs``,
build the HTML documents and static assets, and force add it to the commit for
use with Github Pages.

To build and publish documentation for a release, add the ``gh-pages`` branch
to the ``docs`` folder in your worktree::

  git worktree add -B gh-pages docs origin/gh-pages

In the ``sphinx-docs`` folder, use ``make docs`` to build the HTML documents
and static assets, add it to the docs folder, and commit it for publication on
Github Pages. After the build completes, push to GitHub from the ``docs`` folder.

License
-------
This project is licensed under the `Apache 2.0 License <https://github.com/Princeton-CDH/ppa-django/blob/master/LICENSE>`_.

©2019 Trustees of Princeton University.  Permission granted via
Princeton Docket #20-3624 for distribution online under a standard Open Source
license. Ownership rights transferred to Rebecca Koeser provided software
is distributed online via open source.
