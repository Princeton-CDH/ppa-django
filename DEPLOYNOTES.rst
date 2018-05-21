.. _DEPLOYNOTES:

Deploy and Upgrade notes
========================

0.8 Search filtering and highlighting
-------------------------------------

* The Solr schema has been modified and must be updated::

    python manage.py solr_schema

* The Solr schema change requires reindexing content.  It is
  **recommended** to clear out your Solr index and reindex everything::

    python manage.py index

* A fixture has been provided with site page content.  Load via::

    python loaddata ppa/archive/fixtures/pages.json

.. Note::

  The previous import and index script has been broken into two
  scripts. For a fresh install, run **hathi_import** as before to import
  content into the Django database and then run **index** to index work
  and page content into Solr.


0.5 Bulk Import and Simple Search
---------------------------------

* Configure your database in local settings and run migrations::

    python manage.py migrate

* Create a new Solr core with a basic configuration and managed schema::

    solr create -c SOLR_CORE -n basic_configs

  Configure the Solr core name and urls in local settings, and then update
  the schema::

    python manage.py solr_schema

* Bulk import assumes you already have a local copy of the desired
  HathiTrust materials retrieved via rsync (see https://www.hathitrust.org/datasets).
  Be sure to include pairtree version and prefix files in the rsync data.
  The path to the top directory of the local Hathi data should be
  configured in localsettings as **HATHI_DATA**.  Once the data is present
  and the path is configured, run the import script (with optional
  progress bar)::

    python manage.py hathi_import
    python manage.py hathi_import -v 0 --progress

