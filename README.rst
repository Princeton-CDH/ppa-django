ppa-django
==========

.. sphinx-start-marker-do-not-remove

Django web application for `Princeton Prosody Archive
<https://prosody.princeton.edu/>`_ version 3.x.

Code and architecture documentation for the current release available
at `<https://princeton-cdh.github.io/ppa-django/>`_.

.. image:: https://zenodo.org/badge/110731137.svg
   :target: https://doi.org/10.5281/zenodo.2400705
   :alt: DOI: 10.5281/zenodo.2400705

.. image:: https://github.com/Princeton-CDH/ppa-django/actions/workflows/unit-tests.yml/badge.svg
   :target: https://github.com/Princeton-CDH/ppa-django/actions/workflows/unit-tests.yml
   :alt: Unit test status

.. image:: https://codecov.io/gh/Princeton-CDH/ppa-django/branch/main/graph/badge.svg
   :target: https://codecov.io/gh/Princeton-CDH/ppa-django
   :alt: Code coverage

.. image:: https://www.codefactor.io/repository/github/princeton-cdh/ppa-django/badge
   :target: https://www.codefactor.io/repository/github/princeton-cdh/ppa-django
   :alt: CodeFactor

.. image:: https://requires.io/github/Princeton-CDH/ppa-django/requirements.svg?branch=main
   :target: https://requires.io/github/Princeton-CDH/ppa-django/requirements/?branch=main
   :alt: Requirements Status

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black
   :alt: code style Black

.. image:: https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336
  :target: https://pycqa.github.io/isort/
  :alt: imports: isort

This repo uses `git-flow <https://github.com/nvie/gitflow>`_ conventions; **main**
contains the most recent release, and work in progress will be on the **develop** branch.
Pull requests should be made against develop.


Python 3.6 / Django 3.2 / Node 16.15 / Postgresql 13 / Solr 8


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

- Create a new Solr configset from the files in ``solr_conf`` ::

    cp -r solr_conf /path/to/solr/server/solr/configsets/ppa
    chown solr:solr -R /path/to/solr/server/solr/configsets/ppa

  and configure **SOLR_CONNECTIONS** in local settings with your
  preferred core/collection name and the configset name you created.

  See developer notes for setup instructions for using docker with `solr:8.4` image.

- Bulk import (*provisional*): requires a local copy of HathiTrust data as
  pairtree provided by rsync.  Configure the path in `localsettings.py`
  and then run::

    python manage.py hathi_import

- Then index the imported content into Solr::

    python manage.py index -i work
    python manage.py index_pages

Frontend development setup:

This project uses the `Fomantic UI <https://fomantic-ui.com/>`_ library in
addition to custom styles and javascript. You need to compile static assets
before running the server.

- To build all styles and js for production, including fomantic UI::

    npm install
    npm run build

Alternatively, you can rebuild just the custom files or fomantic independently.
This is useful if you make small changes and need to recompile once::

    npm run build:qa # just the custom files, with sourcemaps
    npm run build:prod # just the custom files, no sourcemaps
    npm run build:semantic # just fomantic UI

Finally, you can run a development server with hot reload if you'll be changing
either set of assets frequently. These two processes are separate as well::

    npm run dev # serve just the custom files from memory, with hot reload
    npm run dev:semantic # serve just fomantic UI files and recompile on changes

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

Note that python unit tests access a test server over HTTP, and therefore
expect static files to be compiled – see "Frontend development setup" above
for how to do this.

In a CI context, we instead use a ``webpack-stats.json`` file that mocks the
existence of the static files so they aren't required. This file is located in
the ``ci/`` directory and needs to be updated if new entrypoints are configured
in ``webpack.config.js``.

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

Setup pre-commit hooks
~~~~~~~~~~~~~~~~~~~~~~

If you plan to contribute to this repository, please run the following command:

    pre-commit install

This will add a pre-commit hook to automatically style your python code with `black <https://github.com/psf/black>`_ and sort your imports with `isort <https://pycqa.github.io/isort/>`_.

Because these styling conventions were instituted after multiple releases of development on this project, ``git blame`` may not reflect the true author of a given line. In order to see a more accurate ``git blame`` execute the following command:

    git blame <FILE> --ignore-revs-file .git-blame-ignore-revs

Or configure your git to always ignore styling revision commits:

    git config blame.ignoreRevsFile .git-blame-ignore-revs

Documentation
-------------

Documentation is generated using `sphinx <http://www.sphinx-doc.org/>`__
To generate documentation them, first install development requirements::

    pip install -r dev-requirements.txt

Then build documentation using the customized make file in the ``docs``
directory::

    cd sphinx-docs
    make html

To check documentation coverage, run::

    make html -b coverage

This will create a file under ``_build/coverage/python.txt`` listing any
python classes or methods that are not documented. Note that sphinx can only
report on code coverage for files that are included in the documentation. If a
new python file is created but not included in the sphinx documentation, it
will be omitted.

Documentation will be built and published with GitHub Pages by a GitHub Actions
workflow triggered on push to ``main``.

The same GitHub Actions workflow will build documentation and checked
documentation coverage on pull requests.

License
-------
This project is licensed under the `Apache 2.0 License <https://github.com/Princeton-CDH/ppa-django/blob/main/LICENSE>`_.

©2019-2023 Trustees of Princeton University.  Permission granted via
Princeton Docket #20-3624 for distribution online under a standard Open Source
license. Ownership rights transferred to Rebecca Koeser provided software
is distributed online via open source.
