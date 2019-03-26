import clearable from '../js/clearable'
import ImageLazyLoader from '../js/modules/LazyLoad'
import PageSearchForm from './modules/PageSearchForm'

$(function(){
    $('.question-popup').popup()
    $('#id_query').get().map(clearable)

    const $$pagePreviews = $('img[data-src]')

    new ImageLazyLoader($$pagePreviews.get()) // lazy load images

    let form = document.getElementById('search-within') as HTMLFormElement
    let rf = new PageSearchForm(form)

})
