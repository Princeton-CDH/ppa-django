Troubleshooting
===============

Local Solr setup
----------------
Install Solr via `brew <https://formulae.brew.sh/formula/solr>`::

  brew install solr

Copy the Solr config files in as a configset named `ppa`::

  cp -r solr_conf /opt/homebrew/opt/solr/server/solr/configsets/ppa

Create symbolic link to configsets in the Solr home directory::

    ln -s /opt/homebrew/opt/solr/server/solr/configsets /opt/homebrew/var/lib/solr/

Create a new core with the `ppa` configset (Solr must be running)::

    curl "http://localhost:8983/solr/admin/cores?action=CREATE&name=ppa&configSet=ppa"

When the configset has changed, copy in the updated Solr config files::

    cp solr_conf/* /opt/homewbrew/var/lib/solr/configsets/ppa/


Solr setup with Docker
----------------------

Create a new docker container with the Solr 9.2 image::

    docker run --name solr92 -p 8983:8983 -t solr:9.2

Copy the solr config files in as a configset named `ppa`::

    docker cp solr_conf solr92:/opt/solr/server/solr/configsets/ppa

Change ownership  of the configset files to the `solr` user::

    docker exec --user root solr92 /bin/bash -c "chown -R solr:solr /opt/solr/server/solr/configsets/ppa"

Copy the configsets to the solr data directory::

    docker exec -d solr92 cp -r /opt/solr/server/solr/configsets /var/solr/data

Create a new core with the `ppa` configset::

    curl "http://localhost:8983/solr/admin/cores?action=CREATE&name=ppa&configSet=ppa"

When the configset has changed, copy in the updated solr config files::

    docker cp solr_conf/* solr92:/var/solr/data/configsets/ppa/

Setup
-----

Solr changes not reflected in search results? ``solrconfig.xml`` must be
updated in Solr's main directory: ``solr/server/solr/[CORE]/conf/solrconfig.xml``


Updating HathiTrust records and generating a fresh text corpus
--------------------------------------------------------------

These commands should be run on the production server as the deploy user
with the python virtual environment activated.

Update all HathiTrust documents with rsync::

    python manage.py hathi_rsync

This file will generate a csv report of the files that were updated.
Use the resulting file to get a list of ids that need to be indexed:

    cut -f 1 -d, ppa_rsync_changes_[TIMESTAMP].csv | sort | uniq | tail -n +2 > htids.txt

Index pages for the documents that were updated via rsync to make sure
Solr has all the updated page content::

    python manage.py index_pages `cat htids.txt`

Generate a new text corpus::

    python manage.py generate_textcorpus

Use rsync to copy the generated corpus output to a local machine and
optionally also upload to TigerData.

If you need to filter the corpus to a smaller set of records, use the
filter utility script in the ppa-nlp repo / corppa python library
(currently in development branch.)


Indexing with multiprocessing
-----------------------------

To run the multiprocessing page index script (`index_pages`) on MacOS versions past High Sierra, you must disable a security feature that restricts multithreading.
Set this environment variable to override it: `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`

For more details, see `stack overflow <https://stackoverflow.com/questions/50168647/multiprocessing-causes-python-to-crash-and-gives-an-error-may-have-been-in-progr/52230415#52230415>`_.


Postgresql setup
---------------

To create a new postgres database and user for development::

    psql -d postgres -c "DROP DATABASE ppa;"
    psql -d postgres -c "DROP ROLE ppa;"
    psql -d postgres -c "CREATE ROLE ppa WITH CREATEDB LOGIN PASSWORD 'ppa';"
    psql -d postgres -U ppa -c "CREATE DATABASE ppa;"

To replace a local development database with a dump of production data::

    psql -d postgres -c "DROP DATABASE cdh_ppa;"
    psql -d postgres -c "CREATE DATABASE cdh_ppa;"
    psql -d postgres -U cdh_ppa < data/13_daily_cdh_ppa_cdh_ppa_2023-01-11.Wednesday.sql


Updating Wagtail test fixture
-----------------------------

We use a fixture in `ppa/common/fixtures/wagtail_pages.json` for some wagtail unit tests.
To update this to reflect changes in new versions of wagtail:

1. Create an empty database to use for migrated the fixture.
2. Check out a version of the codebase before any new migrations have been applied,
and run migrations up to that point on the new database (`python manage.py migrate`)
3. Remove preloaded wagtail content from the database using python console or web interface.
4. Check out the new version of the code with the updated version of wagtail.
5. Run migrations.
6. Exported the migrated fixture data back to the fixture file. It's essential
to use the `--natural-foreign` option::

    ./manage.py dumpdata --natural-foreign wagtailcore.site wagtailcore.page wagtailcore.revision pages editorial auth.User --indent 4 > ppa/common/fixtures/wagtail_pages.json

7. Remove any extra user accounts from the fixture (like `script`)
8. Use `git diff` to check for any other major changes.
