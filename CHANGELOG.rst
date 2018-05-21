.. _CHANGELOG:

CHANGELOG
=========

0.8 Search filtering and highlighting
-------------------------------------

Includes nearly all public-facing functionality documented in the CDH project
charter for minimum viable product (and some additional features), with the
exception of blog/editorial content management functionality and a few other
content management features.  Templates and styles are provisional, focusing
on basic layout and interactions.


Search filters and highlighting
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* As a user viewing keyword search results, I want to see a few text snippets from the full text of a work so that I can get an idea how my search terms are used in the work.
*  As a user viewing an individual item from a keyword search, I want to see page image thumbnails and text snippets that match my search terms so I can see how many and what kind of pages match my search terms.
* As a user, I want to search digitized volumes by keyword in author names in a clearly marked author search field so that I can see what materials are in the archive by a certain author.
* As a user, I want to search digitized volumes by title keywords in a clearly marked title field so that I can see what materials are in the archive with a certain title.
* As a user, I want to change how my results are sorted so I can browse the results in multiple ways.
* As a user, I want to filter search results by publication year or range of years so that I focus on works from a particular time period.
* As a user, I want to see a simple timeline visualization of works by publication year so that I can get a sense of how the materials are distributed by time.
* As a user, I want to see numbered results so I can keep track of results as I’m scrolling and paging through.
* As a user browsing the list of collections, I want to see brief summary statistics so I can decide which collections of materials I want to browse.
* As a user, I want to add all or selected works from the search results list to my Zotero library, so that I can efficiently save them for later research or citation.
* As a user, I want to add a work to my Zotero library from the individual item page so that I can save it for research without having to go back to the list of results.

Basic content management
^^^^^^^^^^^^^^^^^^^^^^^^

* As a content editor, I want to create and edit content pages on the site so that I can update text on the site when information changes.

Other improvements
^^^^^^^^^^^^^^^^^^

* New, more efficient Solr index script
* Templates and basic styles for current site components
* SCSS/JS pipeline with compressor


0.7 Collections Improvements
----------------------------

Minor improvements to collections management and bug fix.

* As an admin, I want a "Collection" column viewable on the "Digitized works" page so that I can easily see what collection(s) an item belongs to.
* As an admin, I want a link from the digitized work list view to HathiTrust so that I can check the contents as I curate the archive.
* Bug fix: Bulk add to collections tool is clearing items that were previously added to collections individually.
  This release resolves this error which resulted from setting rather
  than adding digital works to collections.


0.6 Collections Management
--------------------------

Release adding collections creation and management, as well as CSV exports of all digitized works.

CSV Export
^^^^^^^^^^
* As an admin, I want to generate a CSV report of materials on the site so that I can do analysis with other tools such as OpenRefine to analyze collection assignment.

Collections
^^^^^^^^^^^
* As an admin, I want to create and update collections so that I can group digitized works into subcollections for site users.
* As an admin, I want to add and edit collection descriptions so that I can help site users understand the collection and find related materials.
* As an admin, I want to add individual digitized items to one or more collections so that I can manage which items are included in which collections.
* As an admin, I want a way to search and select digitized items for bulk addition to a collection so that I can efficiently organize large groups of items.
* As a user, I want to browse the list of collections so I can find out more about important groupings of items in the archive.
*  As a user, I want to filter search results by collection so that I can include or exclude groups of materials based on my interests.


0.5 Bulk Import and Simple Search
---------------------------------

Initial release with basic admin functionality, import/index Hathi materials, and a basic search to allow interacting and testing the Solr index.

User Management
^^^^^^^^^^^^^^^
* As a project team member, I want to login with my Princeton CAS account so that I can use existing credentials and not have to keep track of a separate username and password.
* As an admin, I want to edit user and group permissions so I can manage project team member access within the system.
* As an admin, I want an easy way to give project team members archive management and content editing permissions so that I don’t have to keep track of all the individual required permissions.


HathiTrust Materials
^^^^^^^^^^^^^^^^^^^^

* As an admin, I want a bulk import of HathiTrust materials so that previously identified and downloaded data can be added to the system.
* As an admin, I want to see a list of all digitized materials in the archive so that I can view and manage the contents.
* As an admin, I want to see when an item was added to the archive and when it was last modified so that I can see which materials were added and changed and when.
* As an admin, I want to see the history of all edits to a digitized work, including import and updates via script, so that I can track the full history of contributions and changes to the record.
* As a user, I want to search and browse digitized volumes by keyword so that I can see what materials are in the archive.
* As a user, I want to see basic details for individual items in the archive so that I can see the record details and get to the HathiTrust version.
