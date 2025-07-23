.. _DEPLOYNOTES:

Deploy and Upgrade notes
========================

3.15
----
* The footer has been updated such that the Technical page must now be manually set to appear in menus in Wagtail.
* Need to run `./manage.py index -i work` to update the index for the new COinS metadata for Zotero citation.
* DocRaptor API key must be configured in Wagtail settings in order to generate PDFs of Editorial essays.

3.14
----

* Configuration for local page-level OCR for Gale content (**GALE_LOCAL_OCR**) should be updated to reference a directory the formatted content with a single path JSON file.
* EEBO-TCP content can now be imported using the `eebo_import` manage command; this requires the **EEBO_DATA** path to be configured in local settings.
* Gale pages should be indexed periodically so encrypted image urls will be current. It is recommended to use 4 processes (`-p 4`) when indexing on a VM with 2 CPUs, since the API and filesystem reads cause non-computational delays.

3.13.1
------
* To enable Plausible analytics, update local settings to set `INCLUDE_ANALYTICS` to True,
configure the full plausible javascript url with any options you want as `PLAUSIBLE_ANALYTICS_SCRIPT` and optionally enable 404 checking with `PLAUSIBLE_ANALYTICS_404s = True`

3.13
----

* To use local OCR for Gale page content, configure **GALE_LOCAL_OCR** path in local settings.
* This release updates Gale image url logic to rely on image URLs from the API, which are (or will be) encrypted and rotated periodically. 
* Gale pages should be indexed after this deploy to load the new local OCR and to update page image urls, and then periodically via cron job to update page image urls::

  python manage.py index_pages --source Gale

* EEBO-TPC import requires configuring **EEBO_DATA** path in local settings, but it is not recommended to import EEBO-TCP content in this release.

3.12.1
------

This release updates PPA to run against Solr 9, with a new configset.
Solr configuration should be updated and all content should be indexed
into the new Solr 9 core::

    python manage.py index -i work
    python manage.py index_pages


3.12
----

* Settings are now configured with django-split-settings as a module;
  local_settings.py must be moved to ppa/settings/local_settings.py
* Index ids for excerpts have changed; this requires reindexing works
  and pages for excerpts and articles; pages should be indexed
  after running rsync.  To reindex works::

    python manage.py index -i work

* Local pairtree data should be updated for all HathiTrust works::

    python manage.py hathi_rsync

* After pairtree content has been updated, pages should be updated
  in Solr::

    python manage.py index_pages

* Digital page ranges for HathiTrust excerpts should be corrected
  using a CSV file provided by the project team::

    python manage.py adjust_excerpts HT_excerpt_corrections.csv


3.11.2
------

* This version includes a wagtail upgrade, which requires running a script
  to rebuild the references index::

    python manage.py rebuild_references_index

* This version enables wagtail search for content admin functionality. You
  must update the wagtail index::

    python manage.py update_index

3.10
----

* Project contributors with specific years of involvement should be updated to
  move years from their name to the new project years field
* Editorial articles with editors can be updated to specify the editors in the metadata instead of the article text
* Editorial articles can now be updated with DOI.
  - To include a DOI in an editorial PDF: reserve a DOI, add it to the article, create the PDF, then deposit the PDF and publish the DOI
* Editorial articles can link to published PDF versions of the article

3.9
---

* Noted that PUL is running Solr 8.4; tests, documentation, and local environments ought to change accordingly.


3.8
---

* Now using nodejs v16.14; should be installed on destination servers.
  On CentOS, `sudo yum install nodejs-16.15.0` should work.
* Clusters to aggregate groups of works should be imported via `import_clusters`
  script and CSV provided by project team.
* The new work clustering logic requires reindexing all pages::

    python manage.py index_pages


3.7
---

* Gale API client requires **GALE_API_USERNAME** and **MARC_DATA** in local
  settings.

* Gale/ECCO MARC records must be made available for import
  by splitting out binary MARC into a local pairtree storage::

    python manage.py split_marc ECCO1a-prin77918.mrc ECCO1b-prin77918.mrc ECCO2-prin77918.mrc

* Reindex all works and pages to ensure that thumbnails for HathiTrust materials display
  correctly, and pages and works are grouped correctly in search results::

    python manage.py index -i work
    python manage.py index_pages

* Import Gale/ECCO records using the CSV file provided by the project team::

    python manage.py gale_import -c ecco_works.csv

* Convert HathiTrust records to Excerpts or Articles using CSV files provided by the team::

    python manage.py hathi_excerpt hathitrust_excerpts.csv

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
