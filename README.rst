ppa-django
==============

.. sphinx-start-marker-do-not-remove

Django web application for the new `Princeton Prosody Archive
<https://cdh.princeton.edu/princeton-prosody-archive/>`_.

This repo uses `git-flow <https://github.com/nvie/gitflow>`_ conventions; **master**
contains the most recent release, and work in progress will be on the **develop** branch.
Pull requests should be made against develop.


Development instructions
------------------------

Initial setup and installation:

-  **recommended:** create and activate a python 3.5 virtualenv::

     virtualenv ppa -p python3.5
     source ppa/bin/activate

-  Use pip to install required python dependencies::

     pip install -r requirements.txt
     pip install -r dev-requirements.txt

-  Copy sample local settings and configure for your environment::

   cp ppa/local_settings.py.sample ppa/local_settings.py

- Create a database, configure in local settings, and run migrations::

    python manage.py migrate


