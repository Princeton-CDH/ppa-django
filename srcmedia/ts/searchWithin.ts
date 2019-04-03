import clearable from '../js/clearable'
import ImageLazyLoader from '../js/modules/LazyLoad'
import PageSearchForm from './components/PageSearchForm'

document.addEventListener('DOMContentLoaded', () => {

    // selectors
    const $pageSearchForm = document.getElementById('search-within') as HTMLFormElement
    const $pagePreviews = document.querySelectorAll('img[data-src]')

    // components
    const pageSearchForm = new PageSearchForm($pageSearchForm)

    // bindings
    $('.question-popup').popup() // semantic ui popups
    $('#id_query').get().map(clearable) // clearable inputs
    new ImageLazyLoader(Array.from($pagePreviews)) // lazy load images

})
