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

Start Solr by running the following command::

    /opt/homebrew/opt/solr/bin/solr start -f


Local PostgreSQL
----------------
Install PostgreSQL via `brew <https://formulae.brew.sh/formula/postgresql@15>`::

    brew install postgresql@15

Start PostgreSQL (or restart after an ugrade)::

    brew services start postgresql@15

Add PostgreSQL to your PATH::

    echo 'export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"' >> ~/.zshrc


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
    psql cdh_ppa < data/13_daily_cdh_ppa_cdh_ppa_2023-01-11.Wednesday.sql


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


Testing local DocRaptor PDF generation
--------------------------------------

In order for DocRaptor to read any content, you must open your localhost to the
public with a service like Cloudflare Tunnel, e.g.::

    npx cloudflared tunnel --url http://localhost:8000

Then in Wagtail Site settings, set the default Site's hostname to the tunnel's
public hostname (no protocol/slashes), and port 80. That way,
``GeneratePdfPanel.BoundPanel.instance.full_url`` resolves to a public URL.

Finally, set your ALLOWED_HOSTS setting to allow traffic via that domain,
or simply set ``ALLOWED_HOSTS = ["*"]``.

Note that this will not work in Webpack dev mode.

When finished, set the default Site back to ``localhost`` and port 8000.


Upgrading Fomantic UI
---------------------

In order to upgrade to newer versions of Fomantic UI:

1. Bump both ``fomantic-ui`` and ``fomantic-ui-less`` packages to the same
   version number.
2. Replace the contents of ``sitemedia/semantic/src/themes/default`` with the
   new version's ``default`` theme. This can be found either in the
   `Fomantic-UI-LESS repo <https://github.com/fomantic/Fomantic-UI-LESS>`_
   or in ``node_modules/fomantic-ui-less/themes/default`` after installing the
   new version.
3. Check for deprecations or major changes between versions to see if any new
   site or ``theme.config`` variables are required, or if behaviors have
   changed.
4. To test locally, rebuild with ``npm run build`` and collect static files
   with ``python manage.py collectstatic``, then restart your dev server. Then
   you can test the update locally (check styles, fonts, UI behaviors).
