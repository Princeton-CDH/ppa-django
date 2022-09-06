Troubleshooting
===============

Solr setup with Docker
----------------------

Create a new docker container with the Solr 6.6 image::

    docker run --name solr6 -p 8983:8983 -t solr:6.6

Copy the solr config files in as a configset named `ppa`::

    docker cp solr_conf solr6:/opt/solr/server/solr/configsets/ppa

Change ownership  of the configset files to the `solr` user::

    docker exec --user root solr6 /bin/bash -c "chown -R solr:solr /opt/solr/server/solr/configsets/ppa"

Copy the configsets to the solr data directory::

    docker exec -d solr6 cp -r /opt/solr/server/solr/configsets /var/solr/data

Create a new core with the `ppa` configset::

    curl "http://localhost:8983/solr/admin/cores?action=CREATE&name=ppa&configSet=ppa"

When the configset has changed, copy in the updated solr config files::

    docrker cp solr_conf/* solr6:/opt/solr/server/solr/configsets/ppa/

Setup
-----

Trouble launching Solr? Try configuring Java to version 8. Later versions of
Java will cause Solr 6 to time out.

Solr changes not reflected in search results? ``solrconfig.xml`` must be
updated in Solr's main directory: ``solr/server/solr/[CORE]/conf/solrconfig.xml``

We currently do not support Python 3.7 or Solr 7 and above.

Indexing with multiprocessing
-----------------------------

To run the multiprocessing page index script (`index_pages`) on MacOS versions past High Sierra, you must disable a security feature that restricts multithreading.
Set this environment variable to override it: `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`

For more details, see `stack overflow <https://stackoverflow.com/questions/50168647/multiprocessing-causes-python-to-crash-and-gives-an-error-may-have-been-in-progr/52230415#52230415>`_.

