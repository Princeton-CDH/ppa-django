import DateHistogram from './histogram';

$(function(){

    /* dom */
    const $searchForm = $('.form')
    const $sortLinks = $('.sort .item')
    const $clearDatesLink = $('.clear-selection')
    const $histogram = $('#histogram')
    // dates
    let $$minDateInput = $('#id_pub_date_0')
    let $$maxDateInput = $('#id_pub_date_1')
    let $$minDate = $('.min-date')
    let $$maxDate = $('.max-date')
    
    /* functions */
    function changeSort(event) {
        console.log('currently: ', $(event.target).siblings().find('input[checked=""]'))
        $(event.target).siblings().find('input[checked=""]').removeAttr('checked')
        $(event.target).find('input').attr('checked', '')
    }

    function clearDates() {
        $('#publication input').val('')
        $searchForm.submit()
    }

    function updateDates() {
        let minDate = $$minDateInput.val()
        let maxDate = $$maxDateInput.val()
        $$minDate.text(minDate != '' ? minDate : $$minDateInput.attr('placeholder'))
        $$maxDate.text(maxDate != '' ? maxDate : $$maxDateInput.attr('placeholder'))
    }
    
    /* bindings */
    $('.ui.checkbox').checkbox()
    $sortLinks.find('input[checked=""]').parent().addClass('active')
    $sortLinks.find('input[disabled="disabled"]').parent().addClass('disabled')
    $sortLinks.click((e) => {
        changeSort(e)
        $searchForm.submit()
    })

    $clearDatesLink.click(clearDates)

    new DateHistogram($histogram)

    // update min and max pub date on visualization
    updateDates()

})