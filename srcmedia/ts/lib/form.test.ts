import { RxForm } from './form'

describe('RxForm', () => {

    beforeEach(() => {
        document.body.innerHTML = `<form><input type="text" name="query"/></form>`
    })

    it('stores a target for submissions if one is set', () => {
        const $form = document.querySelector('form') as HTMLFormElement
        $form.target = '/myendpoint/'
        const rxf = new RxForm($form)
        expect(rxf.target).toEqual('/myendpoint/')
    })
    
    it('uses the current page as target if none is set', () => {
        window.history.pushState({}, 'form', '/form/') // go to some path /form
        const $form = document.querySelector('form') as HTMLFormElement
        const rxf = new RxForm($form)
        expect(rxf.target).toEqual('/form/') // endpoint should be the path we're on
    })

    it('can reset itself', () => {
        const $form = document.querySelector('form') as HTMLFormElement
        const $input = document.querySelector('input[type=text]') as HTMLInputElement
        const rxf = new RxForm($form)
        $input.value = 'my search'
        rxf.reset()
        expect($input.value).toBe('')
    })
    
    it('can seralize itself', () => {
        const $form = document.querySelector('form') as HTMLFormElement
        const $input = document.querySelector('input[type=text]') as HTMLInputElement
        const rxf = new RxForm($form)
        $input.value = 'my search'
        expect(rxf.serialize()).toEqual('query=my+search')
    })

    it('can update its state', () => {
        const $form = document.querySelector('form') as HTMLFormElement
        const rxf = new RxForm($form)
        const watcher = jest.fn()
        rxf.state.subscribe(watcher)
        rxf.update({ foo: 'bar' })
        expect(watcher).toHaveBeenCalledWith({ foo: 'bar' })
    })

})