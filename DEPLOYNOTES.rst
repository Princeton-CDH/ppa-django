.. _DEPLOYNOTES:

Deploy and Upgrade notes
========================

0.12
----

* Solr field boosting requires an updated ``solrconfig.xml``. Before deploying
  new code, ``solr_conf/solconfig.xml`` should be copied to the core's
  `conf` directory and the core reloaded (or Solr restarted).

* Updated collection search logic and field boosting require reindexing works::

    python manage.py index --works

* Admin functionality for suppressing digitized works requires that the
  Django application have permission to **delete** files and directories
  from the HathiTrust  pairtree data stored in **HATHI_DATA**.

0.11
----

* ``GTAGS_ANALYTICS_ID`` should include the property ID for the site, in order
    to enable Google Analytics on non-preview pages.

0.10
----

* Switching from Mezzanine to Wagtail requires a manual migration *before*
  installing the new version to avoid migration dependency conflicts::

     python manage.py migrate pages zero

* Wagtail provides predefined groups for *Editor* and *Moderator*. Users
  who were previously in the *Content Editor* group should be added
  to one of these, and the *Content Editor* group should be removed.

* To benefit from new logic for cleaning metadata fields on import, the
  HathiTrust import should be run::

    python manage.py hathi_import -v 0 --progress --update

* Solr schema changes for this release require an updated ``solrconfig.xml``
  with additional ``<lib/>`` declarations. Copy ``solr_conf/solrconfig.xml``
  to the Solr core's `conf` directory, and then restart the Solr server
  to enable the new library paths.

  Because this includes a Solr schema field type change that cannot be converted
  automatically, the index must be cleared before changing the schema,
  and then all content must be reindexed::

    python manage.py index --clear all --index none
    python manage.py solr_schema
    python manage.py index

* Run ``python manage.py setup_site_pages`` to create stub pages for all
  site content needed for main site navigation.


0.9
---

* Configure a **TECHNICAL_CONTACT** email address in local settings
  to set a **From** header on requests made against the HathiTrust API.
* Logic for populating local records from HathiTrust has changed; records
  need to be updated::

    python manage.py hathi_import -v 0 --progress --update

* This update requires a Solr schema update and a full reindex; due to changes
  in page indexing, pages must also be cleared from the Solr index::

     python manage.py solr_schema
     python manage.py index --clear pages


0.8 Search filtering and highlighting
-------------------------------------

* The Solr schema has been modified and must be updated::

    python manage.py solr_schema

* The Solr schema change requires reindexing content.  It is
  **recommended** to clear out your Solr index and reindex everything::

    python manage.py index

* A fixture has been provided with site page content.  Load via::

    python manage.py loaddata ppa/archive/fixtures/pages.json

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
