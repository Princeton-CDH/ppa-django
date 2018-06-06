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
    const $$collectionInputs = $('#collections input')

    /* bindings */
    archiveSearchForm.onStateChange = submitForm
    $$clearDatesLink.click(onClearDates)
    $$sortInputs.change(onSortChange)
    $$collectionInputs.change(onCollectionChange)
    $$checkboxes.checkbox() // this is just a standard semantic UI behavior
    onPageLoad() // misc functions that run once on page load
    
    /* functions */
    function submitForm(state) {
        let url = `?${$.param(state)}` // serialize state using $.param to make querystring
        window.history.pushState(state, 'PPA Archive Search', url) // update the URL bar
        let req = fetch(`/archive/${url}`, { // create the submission request
            headers: { // this header is needed to signal ajax request to django
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        req.then(res => res.text()).then(html => { // submit the form and get html back
            $$paginationTop.html($(html).find('.pagination').html()) // update the top pagination
            dateHistogram.data = JSON.parse($(html).find('pre').html()) // update the histogram
            $$resultsCount.html($(html).find('.data .results-count').html()) // update the results count
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
        $$minDateInput[0].dispatchEvent(new Event('input')) // fake input events
        $$maxDateInput[0].dispatchEvent(new Event('input'))
    }

    function onCollectionChange(event) {
        $(event.currentTarget).parent().toggleClass('active')
    }

    function onSortChange(event) {
        $(event.currentTarget).parent().siblings().removeClass('active')
        $(event.currentTarget).parent().addClass('active')
    }

    function onPageLoad() {
        dateHistogram.data = JSON.parse($('.ajax-container pre').html()) // render the histogram initially
        $$sortInputs.filter(':disabled').parent().addClass('disabled') // disable keyword sort if no query
        $$collectionInputs.filter(':disabled').parent().addClass('disabled') // disable empty collections
    }

})