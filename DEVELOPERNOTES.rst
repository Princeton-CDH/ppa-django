Troubleshooting
===============

Solr setup with Docker
----------------------

Note 2022-02-13: PUL is running Solr 8.4. We need to change our tests, documentation, and local environments accordingly.


Create a new docker container with the Solr 8.6 image::

    docker run --name solr86 -p 8983:8983 -t solr:8.6

Copy the solr config files in as a configset named `ppa`::

    docker cp solr_conf solr86:/opt/solr/server/solr/configsets/ppa

Change ownership  of the configset files to the `solr` user::

    docker exec --user root solr86 /bin/bash -c "chown -R solr:solr /opt/solr/server/solr/configsets/ppa"

Copy the configsets to the solr data directory::

    docker exec -d solr86 cp -r /opt/solr/server/solr/configsets /var/solr/data

Create a new core with the `ppa` configset::

    curl "http://localhost:8983/solr/admin/cores?action=CREATE&name=ppa&configSet=ppa"

When the configset has changed, copy in the updated solr config files::

    docker cp solr_conf/* solr86:/opt/solr/server/solr/configsets/ppa/

Setup
-----

Solr changes not reflected in search results? ``solrconfig.xml`` must be
updated in Solr's main directory: ``solr/server/solr/[CORE]/conf/solrconfig.xml``


Indexing with multiprocessing
-----------------------------

To run the multiprocessing page index script (`index_pages`) on MacOS versions past High Sierra, you must disable a security feature that restricts multithreading.
Set this environment variable to override it: `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`

For more details, see `stack overflow <https://stackoverflow.com/questions/50168647/multiprocessing-causes-python-to-crash-and-gives-an-error-may-have-been-in-progr/52230415#52230415>`_.


Postgresql setup
---------------

psql -d postgres -c "DROP DATABASE ppa;"
psql -d postgres -c "DROP ROLE ppa;"
psql -d postgres -c "CREATE ROLE ppa WITH CREATEDB LOGIN PASSWORD 'ppa';"
psql -d postgres -U ppa -c "CREATE DATABASE ppa;"

or

psql -d postgres -c "DROP ROLE cdh_ppa;"
psql -d postgres -c "DROP DATABASE cdh_ppa;"
psql -d postgres -c "CREATE ROLE cdh_ppa WITH CREATEDB LOGIN PASSWORD 'cdh_ppa';"
psql -d postgres -U cdh_ppa < data/13_daily_cdh_ppa_cdh_ppa_2023-01-11.Wednesday.sql