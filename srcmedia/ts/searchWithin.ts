import { map } from 'rxjs/operators'

import clearable from '../js/clearable'
import ImageLazyLoader from '../js/modules/LazyLoad'
import PageSearchForm from './components/PageSearchForm'
import { RxTextInput } from './lib/input'
import { RxOutput } from './lib/output'

document.addEventListener('DOMContentLoaded', () => {

    // selectors ($ denotes ref to HTMLElement)
    const $pageSearchForm = document.getElementById('search-within') as HTMLFormElement
    const $keywordInput = document.querySelector('input[name=query]') as HTMLInputElement
    const $resultsOutput = document.querySelector('output[form=search-within]') as HTMLOutputElement
    const $pagePreviews = document.querySelectorAll('img[data-src]')

    // components
    const pageSearchForm = new PageSearchForm($pageSearchForm)
    const keywordInput = new RxTextInput($keywordInput)
    const resultsOutput = new RxOutput($resultsOutput)

    // bindings
    keywordInput.state.subscribe(pageSearchForm.submit) // submit form when keyword changes
    pageSearchForm.state.pipe(map((state) => state?.results)).subscribe(resultsOutput.update.bind(resultsOutput)) // pass updated results to the output

    // setup
    $('.question-popup').popup() // semantic ui popups
    $('#id_query').get().map(clearable) // clearable inputs
    new ImageLazyLoader(Array.from($pagePreviews)) // lazy load images
})
