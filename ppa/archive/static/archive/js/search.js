import ReactiveForm from './ReactiveForm'
import Histogram from './Histogram'

$(function(){

    /* components */
    const archiveSearchForm = new ReactiveForm('.form')
    const dateHistogram = new Histogram('#histogram')

    /* dom */
    const $$results = $('.ajax-container')
    const $$paginationTop = $('.pagination').first()
    const $$resultsCount = $('.workscount .count')
    const $$clearDatesLink = $('.clear-selection')
    const $$checkboxes = $('.ui.checkbox')
    const $$minDateInput = $('#id_pub_date_0')
    const $$maxDateInput = $('#id_pub_date_1')
    const $$sortInputs = $('.sort input')
    const $$sortSelect = $('.sort .dropdown')
    const $$collectionInputs = $('#collections input')
    const $$textInputs = $('input[type="text"]')
    const $$relevanceSort = $('input[value="relevance"]')
    const $$relevanceOption = $('.sort .dropdown option[value="relevance"]')
    const $$advancedSearchButton = $('.show-advanced')

    /* bindings */
    archiveSearchForm.onStateChange(submitForm)
    $$clearDatesLink.click(onClearDates)
    $$sortInputs.change(onSortChange)
    $$sortSelect.change(onMobileSortChange)
    $$collectionInputs.change(onCollectionChange)
    $$advancedSearchButton.click(toggleAdvancedSearch)
    onPageLoad() // misc functions that run once on page load
    
    /* functions */
    function submitForm(state) {
        let sort = state.filter(field => field.name == 'sort')[0] // save one of the sort values (mobile or desktop); should be identical
        state = state.filter(field => field.value != '').filter(field => field.name != 'sort') // filter out empty fields and the sorts
        state.push(sort) // re-add the sort so there's only one (otherwise would be two values for mobile/desktop)
        if (state.filter(field => $$textInputs.get().map(el => el.name).includes(field.name)).length == 0) { // if no text query,
            $$relevanceSort.prop('disabled', true).parent().addClass('disabled') // disable relevance
            $$relevanceOption.prop('disabled', true) // also disable it on mobile
            if (state.filter(field => field.name == 'sort')[0].value == 'relevance') { // and if relevance had been selected,
                $('input[value="title_asc"]').click() // switch to title instead
                $$sortSelect.val('title_asc').click() // also on mobile
            }
        }
        else {
            $$relevanceSort.prop('disabled', false).parent().removeClass('disabled') // enable relevance sort
            $$relevanceOption.prop('disabled', false) // also enable it on mobile
        }
        let url = `?${$.param(state)}` // serialize state using $.param to make querystring
        window.history.pushState(state, 'PPA Archive Search', url) // update the URL bar
        let req = fetch(`/archive/${url}`, { // create the submission request
            headers: { // this header is needed to signal ajax request to django
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        req.then(res => res.text()).then(html => { // submit the form and get html back
            $$paginationTop.html($(html).find('.pagination').html()) // update the top pagination
            dateHistogram.update(JSON.parse($(html).find('pre.facets').html())) // update the histogram
            $$resultsCount.html($(html).find('pre.count').html()) // update the results count
            $$results.html(html) // update the results
            document.dispatchEvent(new Event('ZoteroItemUpdated', { // notify Zotero of changed results
                bubbles: true,
                cancelable: true
            }))
        })
    }

    function onClearDates() {
        $$minDateInput.val('') // clear the date inputs
        $$maxDateInput.val('')
        $$minDateInput[0].dispatchEvent(new Event('input')) // fake input events to trigger resubmit
        $$maxDateInput[0].dispatchEvent(new Event('input'))
    }

    function onCollectionChange(event) {
        $(event.currentTarget).parent().toggleClass('active')
    }

    function onSortChange(event) {
        $(event.currentTarget).parent().siblings().removeClass('active')
        $(event.currentTarget).parent().addClass('active')
        $$sortSelect.val(event.currentTarget.value).click() // keep main sort in sync with mobile
    }

    function onMobileSortChange(event) {
        $$sortInputs.filter(`[value=${event.target.value}]`).parent().click() // keep main sort in sync with mobile
    }

    function onPageLoad() {
        dateHistogram.update(JSON.parse($('.ajax-container pre.facets').html())) // render the histogram initially
        $$sortInputs.filter(':disabled').parent().addClass('disabled') // disable keyword sort if no query
        $$relevanceOption.prop('disabled', true) // also disable it on mobile
        $$sortSelect.val($$sortInputs.filter(':checked').val()) // set the mobile sort to the same default as the other sort
        $$collectionInputs.filter(':disabled').parent().addClass('disabled') // disable empty collections
        $('.question-popup').popup() // initialize the question popup
        $('.ui.dropdown .dropdown.icon').removeClass('dropdown').addClass('chevron down') // change the icon
        $$checkboxes.checkbox() // this is just a standard semantic UI behavior
        $('.ui.dropdown').dropdown() // same here
    }

    function toggleAdvancedSearch() {
        $('.advanced').slideToggle()
    }

    $$collectionInputs
        .focus(e => $(e.target).parent().addClass('focus')) // make collection buttons focusable
        .blur(e => $(e.target).parent().removeClass('focus')) 
        .keypress(e => { if (e.which == 13) $(e.target).click() }) // pressing enter "clicks" them

})