.. _DEPLOYNOTES:

Deploy and Upgrade notes
========================

3.6
---

* Updates to javascript build tools used to compile fomantic-UI now require that
  the version of nodejs be at least v10. This is already specified via the
  README, but take care that deployment environments respect it or build
  errors will occur.

3.5
---

* Configuration and Solr schema changes are needed, now that PPA uses
  parasolr for Solr schema management and indexing.

  1. Update local settings with the new solr configuration syntax (see
    `local_settings.py.sample`)
  2. Copy all files under `solr_conf` into the `conf` directory of
     a new Solr configset, using the same name you put in local settings.
  3. Run `python manage.py solr_schema` to update (and optionally create)
     your configured Solr core with your configured configset.
  4. Index data into your new solr core::

    python manage.py index -i work
    python manage.py index_pages

* HathiTrust Data API client code has been removed in favor of using rsync.
  Configurations for **HATHITRUST_OAUTH_KEY** and  **HATHITRUST_OAUTH_SECRET**
  are no longer needed in local settings.


3.2
---

* Requires configurations for **HATHITRUST_OAUTH_KEY** and
  **HATHITRUST_OAUTH_SECRET** in order to use HathiTrust Data API
  for adding new items from HathiTrust.

* New functionality for adding items from HathiTrust requires that
  Django application have permission to **add** new files and directories
  from the HathiTrust pairtree data stored in **HATHI_DATA**.

* An update to Solr to include last modification dates for use in
  HTTP response headers requires a schema update and work reindex::

    python manage.py solr_schema
    python manage.py index

3.0.1
-----

* Title searching and boosting requires an update to ``solrconfig.xml``.
  Before deploying new code, ``solr_conf/solconfig.xml`` should be copied
  to the core's `conf` directory and the core reloaded, or Solr restarted.

3.0
---

* Solr field boosting requires an updated ``solrconfig.xml``. Before deploying
  new code, ``solr_conf/solconfig.xml`` should be copied to the core's
  `conf` directory and the core reloaded, or Solr restarted.

* Revised Solr field names, updated collection search logic, and field boosting
  require the index to be cleared and reindexed::

    python manage.py index --clear all --index none
    python manage.py solr_schema
    python manage.py index

* Admin functionality for suppressing digitized works requires that the
  Django application have permission to **delete** files and directories
  from the HathiTrust pairtree data stored in **HATHI_DATA**.

* Adds a new contributor page type, which allows selecting a list of
  people to display as project members and board members. If there is
  an existing contributor content page, it should be removed and
  replaced with a contributor page with the slug `contributor`.


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
