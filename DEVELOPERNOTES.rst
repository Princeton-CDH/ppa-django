Troubleshooting
===============

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


