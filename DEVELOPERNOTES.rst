Troubleshooting
-------------

Trouble launching Solr? Try configuring Java to version 8. Later versions of 
Java will cause Solr 6 to time out.

Solr changes not reflected in search results? ``solrconfig.xml`` must be 
updated in Solr's main directory: ``solr/server/solr/[CORE]/conf/solrconfig.xml``

We currently do not support Python 3.7 or Solr 7 and above.