import DateHistogram from './histogram';

$(function(){

    /* dom */
    const $$searchForm = $('.form')
    const $$sortLinks = $('.sort .item')
    const $$clearDatesLink = $('.clear-selection')
    const $$collectionInputs = $('#collections input');
    const $$histogram = $('#histogram')
    const $$minDateInput = $('#id_pub_date_0')
    const $$maxDateInput = $('#id_pub_date_1')
    const $$minDate = $('.min-date')
    const $$maxDate = $('.max-date')

    /* functions */
    function changeSort(event) {
        $(event.target).siblings().find('input[checked=""]').removeAttr('checked')
        $(event.target).find('input').attr('checked', '')
    }

    function clearDates() {
        // clear both date inputs
        $$minDateInput.val('')
        $$maxDateInput.val('')
        // submit the form
        $$searchForm.submit()
    }

    function updateDates() {
        let minDate = $$minDateInput.val()
        let maxDate = $$maxDateInput.val()
        // if there's a date set, use it - otherwise use the placeholder
        $$minDate.text(minDate != '' ? minDate : $$minDateInput.attr('placeholder'))
        $$maxDate.text(maxDate != '' ? maxDate : $$maxDateInput.attr('placeholder'))
    }


    /* bindings */
    $('.ui.checkbox').checkbox()

    $('.question-popup').popup()

    $$sortLinks.find('input[disabled="disabled"]').parent().addClass('disabled')
    $$sortLinks.click((e) => {
        changeSort(e)
        $$searchForm.submit()
    })

    $$clearDatesLink.click(clearDates)

    new DateHistogram($$histogram)

    // update min and max pub date on visualization
    updateDates()

    $$collectionInputs.filter('[disabled="disabled"]').parent().addClass('disabled')
    $$collectionInputs.change((e) => {
        $(e.target).parent().toggleClass('active')
        $$searchForm.submit()
    })

})