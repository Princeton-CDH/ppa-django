$(function(){

    /* dom */
    const $searchForm = $('.form')
    const $sortLinks = $('.sort .item')
    const $clearDatesLink = $('.clear-selection')
    
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
    $sortLinks.find('input[checked=""]').parent().addClass('active')
    $sortLinks.find('input[disabled="disabled"]').parent().addClass('disabled')
    $sortLinks.click((e) => {
        changeSort(e)
        $searchForm.submit()
    })
    $clearDatesLink.click(clearDates)

})