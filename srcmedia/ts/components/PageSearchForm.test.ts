import 'whatwg-fetch' // used for Response typing
import { Subject } from 'rxjs'

import PageSearchForm from './PageSearchForm'
import { ajax } from '../../js/modules/Utilities'


beforeEach(() => {
    document.body.innerHTML = `
    <form id="search-within">
        <input type="text" name="query" value="mysearch">
    </form>`
})


test('stores state as an observable sequence', () => {
    const $element = document.querySelector('form') as HTMLFormElement
    const psf = new PageSearchForm($element)
    expect(psf.state).toBeInstanceOf(Subject)
})

test('makes an async GET request to its endpoint on submission', done => {
    window.history.pushState({}, 'form', '/form') // to form a full request path
    const $form = document.querySelector('form') as HTMLFormElement
    const psf = new PageSearchForm($form)
    const response = new Response(new Blob(['results!'], { type: 'text/plain' })) // a mock GET response
    jest.spyOn(window, 'fetch').mockImplementation(() => Promise.resolve(response))
    psf.submit().then(() => { // check that we requested the right path, using the right header
        expect(window.fetch).toHaveBeenCalledWith('/form?query=mysearch', ajax)
        done()
    })
})

test('updates its state when it receives results', done => {
    const $form = document.querySelector('form') as HTMLFormElement
    const psf = new PageSearchForm($form)
    const response = new Response(new Blob(['results!'], { type: 'text/plain' }))
    const watcher = jest.fn()
    psf.state.subscribe(watcher)
    jest.spyOn(window, 'fetch').mockImplementation(() => Promise.resolve(response))
    psf.submit().then(() => { // check that we pushed the new results onto state
        expect(watcher).toHaveBeenCalledWith({ results: 'results!' })
        done()
    })
})

test('updates the URL/browser history on submission', done => {
    const $form = document.querySelector('form') as HTMLFormElement
    const psf = new PageSearchForm($form)
    const response = new Response(new Blob(['results!'], { type: 'text/plain' }))
    jest.spyOn(window, 'fetch').mockImplementation(() => Promise.resolve(response))
    psf.submit().then(() => {
        expect(window.location.search).toBe('?query=mysearch') // querystring was changed
        expect(window.history.length).toBeGreaterThan(1) // we added entries to browser history
        done()
    })
})