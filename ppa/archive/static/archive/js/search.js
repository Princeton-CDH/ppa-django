$(function(){

    /* dom */
    const $searchForm = $('.form')
    const $sortLinks = $('.sort .item')
    const $clearDatesLink = $('.clear-selection')
    const $collectionLabels = $('#collections label.button');

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


    /* bindings */
    $('.ui.checkbox').checkbox()
    $sortLinks.find('input[disabled="disabled"]').parent().addClass('disabled')
    $sortLinks.click((e) => {
        changeSort(e)
        $searchForm.submit()
    })
    $collectionLabels.click((e) => {
        $(event.target).toggleClass('active')
        $searchForm.submit()
    })
    $clearDatesLink.click(clearDates)

})