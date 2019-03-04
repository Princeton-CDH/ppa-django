import clearable from './clearable'
import ImageLazyLoader from './modules/LazyLoad'

$(function(){
    const $$pagePreviews = $('img[data-src]')

    $('#id_query').get().map(clearable)
    $('.question-popup').popup()

    new ImageLazyLoader($$pagePreviews.get()) // lazy load images
})
