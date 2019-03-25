import clearable from '../js/clearable'
import ImageLazyLoader from '../js/modules/LazyLoad'
import KeywordSearch from './modules/KeywordSearch'

$(function(){
    $('.question-popup').popup()
    $('#id_query').get().map(clearable)

    const $$pagePreviews = $('img[data-src]')

    new ImageLazyLoader($$pagePreviews.get()) // lazy load images
})
