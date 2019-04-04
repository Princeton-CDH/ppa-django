import { Subject } from 'rxjs'

import { RxInput, RxTextInput, RxCheckboxInput } from './input'
import { exec } from 'child_process';

describe('RxInput', () => {

    beforeEach(() => {
        document.body.innerHTML = `<input type="text">`
    })

    test('stores state as an observable sequence', () => {
        class RxFooInput extends RxInput { } // create a fake subclass
        const element = document.querySelector('input[type=text]') as HTMLInputElement
        const rfi = new RxFooInput(element)
        expect(rfi.state).toBeInstanceOf(Subject)
    })

    test('can update its value', () => {
        class RxFooInput extends RxInput { }
        const element = document.querySelector('input[type=text]') as HTMLInputElement
        const rfi = new RxFooInput(element)
        rfi.update({ value: 'sesame' }).then(() => {
            expect(element.value).toBe('sesame')
        })
    })

    test('can update its name', () => {
        class RxFooInput extends RxInput { }
        const element = document.querySelector('input[type=text]') as HTMLInputElement
        const rfi = new RxFooInput(element)
        rfi.update({ name: 'cracker' }).then(() => {
            expect(element.name).toBe('cracker')
        })
    })

})

describe('RxTextInput', () => {

    beforeEach(() => {
        document.body.innerHTML = `<input type="text">`
    })

    test('updates when the user types into it', done => {
        const element = document.querySelector('input[type=text]') as HTMLInputElement
        const rti = new RxTextInput(element)
        rti.state.subscribe(state => { // set up so that test completes once state is updated
            expect(state).toEqual({ name: '', value: 'mysearch' })
            expect(element.value).toBe('mysearch')
            done() // done() is needed for async tests so we know when to expect the result
        })
        element.value = 'mysearch'
        element.dispatchEvent(new Event('input')) // fake an input event as though the user typed
    })

    test('debounces rapid changes when the user is typing', done => {
        const element = document.querySelector('input[type=text]') as HTMLInputElement
        const rti = new RxTextInput(element)
        const watcher = jest.fn()
        rti.state.subscribe(watcher)
        rti.state.subscribe(() => {
            expect(watcher).toHaveBeenCalledTimes(1) // only called once
            expect(watcher).toHaveBeenCalledWith({ name: '', value: 'mys' }) // only used the final value
            done()
        })
        element.value = 'm'
        element.dispatchEvent(new Event('input'))
        element.value = 'my'
        element.dispatchEvent(new Event('input'))
        element.value = 'mys'
        element.dispatchEvent(new Event('input'))
    })

})

describe('RxCheckboxInput', () => {

    beforeEach(() => {
        document.body.innerHTML = `<input type="checkbox">`
    })

    test('updates when the user toggles it', done => {
        const element = document.querySelector('input[type=checkbox]') as HTMLInputElement
        const rci = new RxCheckboxInput(element)
        rci.state.subscribe(state => {
            expect(state).toEqual({ name: '', checked: true, value: 'on' }) // 'on' is the default value
            expect(element.checked).toBe(true)
            done()
        })
        element.checked = true
        element.dispatchEvent(new Event('change')) // fake a change event as though the user toggled it
    })

})