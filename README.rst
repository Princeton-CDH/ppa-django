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

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black
   :alt: code style Black

This repo uses `git-flow <https://github.com/nvie/gitflow>`_ conventions; **main**
contains the most recent release, and work in progress will be on the **develop** branch.
Pull requests should be made against develop.


Python 3.12 / Django 5.2 / Node 18.12 / Postgresql 15 / Solr 9


Development instructions
------------------------

Initial setup and installation:

- **recommended:** create and activate a python 3.11 virtual environment, perhaps with ``virtualenv`` or ``venv``

- Use pip to install required python dependencies::

   pip install -r requirements.txt
   pip install -r dev-requirements.txt

- Copy sample local settings and configure for your environment::

   cp ppa/settings/local_settings.py.sample ppa/settings/local_settings.py

- Create a database, configure in local settings in the `DATABASES` dictionary, change `SECRET_KEY`, and run migrations::

    python manage.py migrate

- Create a new Solr configset from the files in ``solr_conf`` ::

    cp -r solr_conf /path/to/solr/server/solr/configsets/ppa
    chown solr:solr -R /path/to/solr/server/solr/configsets/ppa

  and configure **SOLR_CONNECTIONS** in local settings with your
  preferred core/collection name and the configset name you created.

  See developer notes for setup instructions for using docker with `solr:8.4` image.

- Bulk import (*provisional*): requires a local copy of HathiTrust data as
  pairtree provided by rsync.  Configure the path in `local_settings.py`
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

With the following alternative npm scripts, you can choose whether or not to
include sourcemaps::

    npm run build:qa # just the custom files, with sourcemaps
    npm run build:prod # just the custom files, no sourcemaps

Finally, you can run a development server with hot reload if you'll be changing
assets frequently::

    npm run dev # serve built code from memory, with hot reload

Tests
~~~~~

Python unit tests are written with `pytest <http://doc.pytest.org/>`_ but use
Django fixture loading and convenience testing methods when that makes
things easier. To run them, first install development requirements::

    pip install -r dev-requirements.txt

To run all python unit tests, use:  `pytest`

Some deprecation warnings for dependencies have been suppressed in
pytest.ini; to see warnings, run with `pytest -Wd`.

Make sure you configure a test solr connection and set up an empty
Solr core using the same instructions as for the development core.

Some python unit tests access rendered views, and therefore
expect static files to be compiled; see "Frontend development setup" above
for how to do this.

In a CI context, we use a fake webpack loader backend that ignores missing assets.

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

This will add a pre-commit hook to automatically style and clean python code with `black <https://github.com/psf/black>`_ and `ruff <https://beta.ruff.rs/docs/>`_.

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

©2019-2024 Trustees of Princeton University.  Permission granted via
Princeton Docket #20-3624 for distribution online under a standard Open Source
license. Ownership rights transferred to Rebecca Koeser provided software
is distributed online via open source.
