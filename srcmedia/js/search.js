import ReactiveForm from './ReactiveForm'
import Histogram from './Histogram'
import clearable from './clearable'
import ImageLazyLoader from './modules/LazyLoad'

$(function(){

    /* components */
    const archiveSearchForm = new ReactiveForm('.form')
    const dateHistogram = new Histogram('#histogram')

    /* dom */
    const $$results = $('.ajax-container')
    const $$paginationTop = $('.page-controls').first()
    const $$resultsCount = $('.workscount .count')
    const $$clearDatesLink = $('.clear-selection')
    const $$minDateInput = $('#id_pub_date_0')
    const $$maxDateInput = $('#id_pub_date_1')
    const $$sortDropdown = $('#sort')
    const $$sortInput = $('#sort input')
    const $$collectionInputs = $('#collections input')
    const $$textInputs = $('input[type="text"]')
    const $$relevanceOption = $('#sort .item[data-value="relevance"]')
    const $$advancedSearchButton = $('.show-advanced button')
    const $$pagePreviews = $('img[data-src]')

    /* bindings */
    archiveSearchForm.onStateChange(submitForm)
    $$clearDatesLink.click(onClearDates)
    $$advancedSearchButton.click(toggleAdvancedSearch)
    $$textInputs.keyup(onTextInputChange)

    new ImageLazyLoader($$pagePreviews.get()) // lazy load images

    onPageLoad() // misc functions that run once on page load

    $$collectionInputs
        .focus(e => $(e.target).parent().addClass('focus')) // make collection buttons focusable
        .blur(e => $(e.target).parent().removeClass('focus'))
        .change(e => $(e.target).parent().toggleClass('active'))
        .keypress(e => { if (e.which == 13) $(e.target).click() }) // pressing enter "clicks" them

    /* functions */
    function submitForm(state) {
        if (!validate()) return // don't submit an invalid form
        state = state.filter(field => field.value != '') // filter out empty fields
        if (state.filter(field => field.name == 'collections').length == 0) { // if the user manually turned off all collections...
            state.push({ name: "collections", value: "" }) // add a blank value to indicate that specific case
        }
        let url = `?${$.param(state)}` // serialize state using $.param to make querystring
        window.history.pushState(state, 'PPA Archive Search', url) // update the URL bar
        let req = fetch(`/archive/${url}`, { // create the submission request
            headers: { // this header is needed to signal ajax request to django
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        $('.workscount').addClass('loading') // turn on the loader
        req.then(res => res.text()).then(html => { // submit the form and get html back
            $$paginationTop.html($(html).find('.page-controls').html()) // update the top pagination
            updateHistogram(JSON.parse($(html).find('pre.facets').html())) // update the histogram
            $$resultsCount.html($(html).find('pre.count').html()) // update the results count
            $$results.html(html) // update the results
            document.dispatchEvent(new Event('ZoteroItemUpdated', { // notify Zotero of changed results
                bubbles: true,
                cancelable: true
            }))
            $('.workscount').removeClass('loading') // turn off the loader
            new ImageLazyLoader($('img[data-src]').get()) // re-bind lazy loaded images
        })
        advancedSearchIndicator()
    }

    function validate() {
        if (!$$minDateInput[0].checkValidity() || !$$maxDateInput[0].checkValidity()) {
            $('.validation').css('visibility', 'visible')
            return false
        }
        // validate that min occurs before max when both are set
        if ($$minDateInput.val() && $$maxDateInput.val() &&
            $$minDateInput.val() > $$maxDateInput.val()) {
            $('.validation').css('visibility', 'visible')
            return false
        }
        $('.validation').css('visibility', 'hidden')
        return true
    }

    function onClearDates() {
        $$minDateInput.val('') // clear the date inputs
        $$maxDateInput.val('')
        $$minDateInput[0].dispatchEvent(new Event('input')) // fake input events to trigger resubmit
        $$maxDateInput[0].dispatchEvent(new Event('input'))
    }

    function onTextInputChange(event) {
        // update sort options based on changes to text input fields

        // if any text inputs now have content
        if ($$textInputs.get().filter(el => $.trim($(el).val()) != '').length) {
            // enable and select relevance sort
            $$relevanceOption.removeClass('disabled')
            $$sortDropdown.dropdown('set selected', 'relevance')

        // no text inputs have content now
        } else {
            // disable relevance sort option
            $$relevanceOption.addClass('disabled')
            // if relevance sort was selected, set back to title
            let sort = archiveSearchForm.state.find(field => field.name == 'sort')
            if (sort && sort.value == 'relevance') {
                $$sortDropdown.dropdown('set selected', 'title_asc')
            }
        }
    }

    function onPageLoad() {
        updateHistogram(JSON.parse($('.ajax-container pre.facets').html())) // render the histogram initially
        $$collectionInputs.filter(':disabled').parent().addClass('disabled') // disable empty collections
        $('.question-popup').popup() // initialize the question popup
        $$sortDropdown.dropdown('setting', {
            onChange: () => $$sortInput[0].dispatchEvent(new Event('input')) // make sure sort changes trigger a submission
        })
        $('.form').keydown(e => { if (e.which === 13) e.preventDefault() }) // don't allow enter key to submit the search
        $$textInputs.each((_, el) => clearable(el)) // make text inputs clearable
        validate()
        if (sessionStorage.getItem('ppa-adv-search') == 'open') { // open advanced search without animating it
            $('.show-advanced').addClass('active')
            $('.advanced.segment').css('display', 'flex')
            $('.advanced.column').css('display', 'inline-block')
        }
        advancedSearchIndicator()
    }

    function advancedSearchOn() {
        $('.show-advanced').addClass('active')
        $('.advanced.segment').css('display', 'flex') // if we don't manually set flex here, jQuery can't infer it
        $('.advanced.column').css('display', 'inline-block') // column shouldn't be flex
        $('.advanced').hide().slideDown() // hide sets display to none while animating
        sessionStorage.setItem('ppa-adv-search', 'open') // remember the value for this session
    }

    function advancedSearchOff() {
        $('.show-advanced').removeClass('active')
        $('.advanced').slideUp()
        sessionStorage.setItem('ppa-adv-search', 'closed')
    }

    function toggleAdvancedSearch() {
        $('.advanced').is(':hidden') ? advancedSearchOn() : advancedSearchOff()
    }

    function advancedSearchIndicator() { // if any adv. search fields are active, show it
        if ($('.advanced input').get().map(e => e.value).find(v => v != '')) {
            $('.show-advanced .search-active').fadeIn()
        }
        else {
            $('.show-advanced .search-active').fadeOut()
        }
    }

    function updateHistogram(counts) { // don't pass nonexistent data to the histogram
        if (counts) {
            dateHistogram.update(counts)
        }
    }

    bodymovin.loadAnimation({ // set up the loader animation
        container: document.getElementById('bm'),
        renderer: 'svg',
        loop: true,
        autoplay: true,
        path: '/static/img/loader/searchLoading.json'
    })
})
