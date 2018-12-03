import clearable from './clearable'

$(function(){
    $('#id_query').get().map(clearable)
    $('.question-popup').popup()
})