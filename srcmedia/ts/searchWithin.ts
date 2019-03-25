import clearable from '../js/clearable'
import ImageLazyLoader from '../js/modules/LazyLoad'
import KeywordSearch from './modules/KeywordSearch'

$(function(){
    const $$pagePreviews = $('img[data-src]')

    $('#id_query').get().map(clearable)
    $('.question-popup').popup()

    new ImageLazyLoader($$pagePreviews.get()) // lazy load images

    // new KeywordSearch('')
})
