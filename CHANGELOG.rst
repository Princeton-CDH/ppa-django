.. _CHANGELOG:

CHANGELOG
=========

0.10.0
------

* As a content editor, I want unneeded punctuation removed when importing or updating records from HathiTrust metadata, so that records are easier to search and browse.
* As a user, I want item titles to be case-insensitive when sorting, so that I can find content alphabetically.
* As a user, I want my search input for publication year to be validated in the browser so that I can't enter invalid dates.

Content management updates
^^^^^^^^^^^^^^^^^^^^^^^^^^

* As a content editor, I want to arrange content pages on the site so that I can update site navigation when information changes. #98
* As an admin, I want the site to provide XML sitemaps for content pages, collection and archive pages, and digitized works so that site content will be findable by search engines.
* Replace Mezzanine with Wagtail as content management system.
* Add built-in fixtures to create default page structure within Wagtail.

Design updates
^^^^^^^^^^^^^^

* Refactor SCSS and media queries.
* Fixes issues with histogram and pub date display on Chrome.
* Fixes an issue where hitting back on a search could result in unformatted JSON being displayed.

0.9.0
-----

* As an admin, I would like to be able to see the Hathi Catalog IDs for a volume so that I can see how individual volumes are grouped together within the HathiTrust.
* As an admin, I want the CSV report of materials on the site to include items' Hathi catalog ID so that I can identify duplicates and multi-volume works.
* As an admin, I want changes made to digitized works and collections in the admin interface to automatically update the public search, so that content in the search and admin interface stay in sync.
* As an admin, I want subtitle and sort title populated from HathiTrust MARCXML so that the records can be displayed and sorted better.
* As a content editor, I want to add edition notes so that I can document the copy of an item that's in the archive.
* As a user, I want to see notes on a digitized work's edition so that I'm aware of the specifics of the copy in PPA.
* As a user, I want to be able to view a page in Hathitrust by clicking its thumbnail or page number in a search result so that I can quickly and easily see my search result in its full context.
* As a user, I want different styles for the main title and subtitle on search results so that I can visually distinguish titles.
* As a user, I want item titles to ignore definite articles and punctuation when sorting, so that I can find the most relevant content first.

Design updates
^^^^^^^^^^^^^^

* Updates styles site-wide to match new designs for most pages
* Fixes some issues with min/max date display on publication date histogram
* Mutes the look of collection "badges" on search results
* Adjusts the interactive area and cursor used for search sorting
* Fixes an issue with sizing of the footer in WebKit browsers

0.8.1
-----

Minor updates, tweaks, and fixes:

* Set HathiTrust links to open in new browser window or tab
* Fix collection search link from individual work detail page
* Style/template updates for pagination links and highlight text on mobile
* Clean up print statements and documentation in hathi import and deploy notes
* Tweak wording to clarify Zotero functionality

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
* As a user viewing an individual item from a keyword search, I want to see page image thumbnails and text snippets that match my search terms so I can see how many and what kind of pages match my search terms.
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
