.. _CHANGELOG:

CHANGELOG
=========

3.5
---

* bugfix: refactor add new works from HathiTrust admin functionality to use rsync instead of API to work around restrictions on Google digitized
* bugfix: improve overly-aggressive keyword search stemming
* bugfix: remove page data from search index when suppressing works
* New manage command ``index_pages`` to reindex pages more efficiently using multiprocessing
* Refactored to use parasolr instead of SolrClient

3.4
---

* Add required alternative text field to captioned image for wagtail content
* Upgrade to Django 2.2
* Upgrade to Wagtail 2.7
* bugfix: correct style regression for side by side images in wagtail content

3.3
---

* As a content editor, I want to create linkable anchors in documents so that I can reference specific sections of my content on other pages.
* As a content editor, I want to add SVG images to content pages so that I can include data visualizations and other scalable images.
* As a content editor, I want to embed external content in editorial and other pages, so that I can include dynamic content in essays.
* Update captioned image to require contextual alternative text
* Preliminary manage command to generate a token-count corpus; implemented by @vineetbansal


3.2.4
-----

Maintenance release.

* Update to pucas 0.6 and current version of django-cas-ng
* Update to pytest 5.x
* Security updates for npm packages


3.2.2
-----

* Update 500 error logo image for consistent color order/overlap
* Add citation metadata to editorial content pages
* bugfix: handle multiple rows of side-by-side images in wagtail content
* bugfix: editorial list page margin fix for even-numbered last child on
  mobile

3.2.1
-----

* Updates the homepage graphic and favicon/logo images to use the filled-in logo.
* Updates the loading animation on the archive search to use an animated .gif.
* Sets the last-modified date for the archive search to match the most recently modified work in the index.

3.2
---

Adds support for adding HathiTrust items to the archive in bulk. Adds reactivity
to the search within work page. Makes numerous improvements to the Wagtail editor
for writing and styling editorial content.

* As a content editor, I want to control how my images are positioned relative to other content so that I can flow text around images and position images side-by-side.
* As a content editor, I want to insert block quotes into the page so that I can use a special style to highlighted quoted material.
* As a user, I want my search results within a work to be loaded as soon as I enter a search term so that my search experience is consistent across pages.
* As an admin, I want to add one or several new items from HathiTrust with a script so that I can add content to the site if I identify something that should be included in the archive.
* As an admin, I want to add one or several new items from HathiTrust via the admin interface so that I can add content to the site if I identify something that should be included in the archive.
* Fixes editorial list page so that newest essays appear first.
* Unifies the available Image block types in the Wagtail editor.
* Adds Wand as a required dependency for animated gif support in Wagtail.
* Fixes an issue with zipfile paths on Windows.
* Adds support for last-modified headers on archive list and detail views.

`3.2 GitHub milestone <https://github.com/Princeton-CDH/ppa-django/milestone/9?closed=1>`_

3.1
---

Support for preserving local edits to metadata, add photos to contributor
content page, and numerous accessibility and style fixes and improvements.

* As an admin, I want to correct basic item-level metadata errors and preserve those corrections so that I can override discrepancies in source materials for display on the site.
* As a content editor, I want to be able to add a photo to a contributor so that users can associate a face with a name and role.
* HathiTrust page image improvements: use Hathi thumbnail API where possible
 (lower res thumbnail), use lazy loading to improve performance and
 reduce likelihood of throttling.
* bugfix: handle bad collection id on archive search page
* Accessibility improvements:
  * improve keyboard navigation
  * fix pages with missing level 1 heading
  * Archive search page accessibility improvements
* Style fixes and improvements:
  * Update contributor page styles and templates to include photos
  * New placeholder image for page images and contributors without photo
  * bugfix: Homepage logo placement is broken without javascript
  * bugfix: Search loading animation layout is broken in Firefox
  * Footer link spacing, mobile improvements for tile display and scrolling on iOS,

`3.1 GitHub milestone <https://github.com/Princeton-CDH/ppa-django/milestone/8?closed=1>`_

3.0.1
-----

* bugfix: Archive title search field should also search subtitle
* As a user, I want search results from the title field to prioritize
  unstemmed matches and boost title over subtitle.
* bugfix: Collections set to be excluded by default are not excluded
  on archive page first loaded
* Style and template fixes and improvements
  * Improved head metadata for Twitter and OpenGraph previews
  * Add styles for <h4> in content pages
  * Consistent link styles across all site content pages
  * Editorial list page styles match other site pages
  * Template tag to add current date and software version to citation page
* Security and performance improvements
  * Implement HTTP strict transport security (HSTS)
  * Remove unused Semantic UI components

3.0 - Initial public version (soft launch)
------------------------------------------

**PPA 3.0 is a completely new implementation of the Princeton Prosody
Archive project. The 3.0 is used here for what would normally be a 1.0 release
as a way to credit and differentiate from previous versions of PPA.**

Admin & data curation functionality
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
* As an admin, I want to manually enter bibliographic information into editable fields so that users can view and search citations for works not available in Hathi.
* As an admin, I want to suppress items from the site so that I can pull content that should not be included or was wrongly added as I am going through and assigning collections to archive volumes.


Search improvements
^^^^^^^^^^^^^^^^^^^
* As a user, I want keyword searches to prioritize matches in the author, title and public notes fields so that I can easily find works using keywords.
* As a user, I should not see suppressed items in search results or item display so that my results are not cluttered by items not meant to be part of the archive.
* As a user, I want to exclude or include items from any of the collections in PPA so that I can refine my search to include relevant items.
* As a user, I want the advanced search pulldown state that I have selected to be preserved when I reload the page so that my view of the search form is stable and consistent without having to continually modify my selection.
* Automatically change default sort to Relevance for keyword searches
* Change `srcid` to `source_id` for fielded search
* bugfix: non-sequential publication dates break search validation
* bugfix: Using actual numbers for date range causes works without
  a date to go missing when form is submitted

Content management
^^^^^^^^^^^^^^^^^^
* As a content editor, I want to be able to add and order multiple authors to an editorial so I can correctly attribute work.
* As a content editor, I want to list people who contributed to the project so that I can give credit to everyone who was involved in it.

UI/UX/Design updates
^^^^^^^^^^^^^^^^^^^^
* Refinements to the search form
  - collapsible advanced search, hidden by default
  - visual indicator if filters are active in the advanced search
  - revised styles for collection filters
* Indicator for search in-progress
* Add a "jump to top" button on search results
* Styles for editorial list page, editorial post including image captions
  and footnotes
* Updated error pages

`3.0 GitHub milestone <https://github.com/Princeton-CDH/ppa-django/milestone/7?closed=1>`_

0.11
----

* As a content editor, I want to control how the description of my editorial content is displayed when on PPA, when shared, and when searched.
* As a content editor, I want to add new or edit existing editorial content so that I can publish and promote scholarly work related to the project.
* As an admin, I should not be able to edit wagtail content in the Django admin so that I don't uninintentionally break content by editing it in the wrong place.

Bugs/chores
^^^^^^^^^^^

* Constrains image sizes in editorial posts
* Sets up Google Analytics
* Fixes an issue with incorrect facet data from Solr for certain date ranges
* Switches to sans-serif font (Open Sans) sitewide
* Adds tzinfo to mysql to fix failing tests in CI

Design updates
^^^^^^^^^^^^^^

* Homepage
* Top navigation menu
* Content pages
* Collections list page
* Search sorting and pagination
* Archive search page
* Digitized work detail page
* Editorial post list page

`0.11 GitHub milestone <https://github.com/Princeton-CDH/ppa-django/milestone/6?closed=1>`_

0.10
----

* As a content editor, I want unneeded punctuation removed when importing or updating records from HathiTrust metadata, so that records are easier to search and browse.
* As a user, I want item titles to be case-insensitive when sorting, so that I can find content alphabetically.
* As a user, I want my search input for publication year to be validated in the browser so that I can't enter invalid dates.

Content management updates
^^^^^^^^^^^^^^^^^^^^^^^^^^

* As a content editor, I want to arrange content pages on the site so that I can update site navigation when information changes.
* As an admin, I want the site to provide XML sitemaps for content pages, collection and archive pages, and digitized works so that site content will be findable by search engines.
* Replace Mezzanine with Wagtail as content management system.
* Add built-in fixtures to create default page structure within Wagtail.

Design updates
^^^^^^^^^^^^^^

* Refactor SCSS and media queries.
* Fixes issues with histogram and pub date display on Chrome.
* Fixes an issue where hitting back on a search could result in unformatted JSON being displayed.

`0.10 GitHub milestone <https://github.com/Princeton-CDH/ppa-django/milestone/5?closed=1>`_

0.9
---

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

`0.9 GitHub milestone <https://github.com/Princeton-CDH/ppa-django/milestone/4?closed=1>`_

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

`0.8 GitHub milestone <https://github.com/Princeton-CDH/ppa-django/milestone/3?closed=1>`_

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

`0.6 GitHub milestone <https://github.com/Princeton-CDH/ppa-django/milestone/2?closed=1>`_

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

`0.5 GitHub milestone <https://github.com/Princeton-CDH/ppa-django/milestone/1?closed=1>`_
