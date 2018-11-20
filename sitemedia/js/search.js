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
    const $$sortDropdown = $('#sort')
    const $$collectionInputs = $('#collections input')
    const $$textInputs = $('input[type="text"]')
    const $$relevanceOption = $('option[value="relevance"]')
    const $$advancedSearchButton = $('.show-advanced')

    /* bindings */
    archiveSearchForm.onStateChange(submitForm)
    $$clearDatesLink.click(onClearDates)
    $$collectionInputs.change(onCollectionChange)
    $$advancedSearchButton.click(toggleAdvancedSearch)
    onPageLoad() // misc functions that run once on page load

    $$collectionInputs
        .focus(e => $(e.target).parent().addClass('focus')) // make collection buttons focusable
        .blur(e => $(e.target).parent().removeClass('focus')) 
        .keypress(e => { if (e.which == 13) $(e.target).click() }) // pressing enter "clicks" them
    
    /* functions */
    function submitForm(state) {
        if (!validate()) return
        state = state.filter(field => field.value != '') // filter out empty fields
        if (state.filter(field => $$textInputs.get().map(el => el.name).includes(field.name)).length == 0) { // if no text query,
            $$relevanceOption.prop('disabled', true) // disable relevance
            if (state.filter(field => field.name == 'sort')[0].value == 'relevance') { // and if relevance had been selected,
                $$sortDropdown.val('title_asc').click() // switch to title instead
            }
        }
        else {
            $$relevanceOption.prop('disabled', false) // enable relevance sort
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

    function validate() {
        if (!$$minDateInput[0].checkValidity() || !$$maxDateInput[0].checkValidity()) {
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

    function onCollectionChange(event) {
        $(event.currentTarget).parent().toggleClass('active')
    }

    function onPageLoad() {
        $$sortDropdown.val($$sortDropdown.find('option:selected').val())
        dateHistogram.update(JSON.parse($('.ajax-container pre.facets').html())) // render the histogram initially
        $$relevanceOption.prop('disabled', true) // also disable it on mobile
        $$collectionInputs.filter(':disabled').parent().addClass('disabled') // disable empty collections
        $('.question-popup').popup() // initialize the question popup
        $$checkboxes.checkbox() // this is just a standard semantic UI behavior
        $$sortDropdown.dropdown() // same here
        $('.form').keydown(e => { if (e.which === 13) e.preventDefault() }) // don't allow enter key to submit the search
        $$textInputs.each(addClearButton)
        $$textInputs.on('input', onTextInput)
        validate()
    }

    function toggleAdvancedSearch() {
        $('.advanced').slideToggle()
    }

    function addClearButton(_, el) {
        let clearButton = $('<i/>', { class: 'clear times icon' })
        let clearField = () => { // called when the icon is clicked
            $(el).val('') // empty the field
            el.dispatchEvent(new Event('input')) // fake input to trigger resubmit
        }
        $(el).val() == '' ? clearButton.hide() : clearButton.show() // if the field is pre-populated, show it
        clearButton.click(clearField) // clicking it clears the field
        clearButton.insertAfter(el)
    }

    function onTextInput(event) {
        // if the input was cleared out, hide the clear button, otherwise show it
        let clearButton = $(event.target).parent().find('.clear.icon')
        $(event.target).val() == '' ? clearButton.hide() : clearButton.show()
    }
})