import { RxForm } from './form'

describe('RxForm', () => {

    beforeEach(() => {
        document.body.innerHTML = `<form><input type="text" name="query"/></form>`
    })

    test('it stores a target for submissions', () => {
        window.history.pushState({}, 'form', '/form/') // go to some path /form
        const $form = document.querySelector('form') as HTMLFormElement
        const rxf = new RxForm($form)
        expect(rxf.target).toEqual('/form/') // endpoint should be the path we're on
    })

    test('can reset itself', () => {
        const $form = document.querySelector('form') as HTMLFormElement
        const $input = document.querySelector('input[type=text]') as HTMLInputElement
        const rxf = new RxForm($form)
        $input.value = 'my search'
        rxf.reset()
        expect($input.value).toBe('')
    })
    
    test('can seralize itself', () => {
        const $form = document.querySelector('form') as HTMLFormElement
        const $input = document.querySelector('input[type=text]') as HTMLInputElement
        const rxf = new RxForm($form)
        $input.value = 'my search'
        expect(rxf.serialize()).toEqual('query=my+search')
    })

    test('can update its state', () => {
        const $form = document.querySelector('form') as HTMLFormElement
        const rxf = new RxForm($form)
        const watcher = jest.fn()
        rxf.state.subscribe(watcher)
        rxf.update({ foo: 'bar' })
        expect(watcher).toHaveBeenCalledWith({ foo: 'bar' })
    })

})