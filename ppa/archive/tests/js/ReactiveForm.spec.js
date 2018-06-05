import { Observable, merge } from 'rxjs'

import ReactiveForm from '../../static/archive/js/ReactiveForm'

describe('Reactive Form', () => {

    beforeAll(() => {
        // create test DOM
        $('body').append('<form class="reactive">\
            <input type="text" name="query">\
            <input type="number" name="date">\
            <input type="checkbox" name="bool">\
            <input type="radio" name="choice" value="optionOne">\
            <input type="radio" name="choice" value="optionTwo">\
        </form>')
    })
    
    describe('constructor()', () => {
        it('should retrieve the associated form element', () => {
            let rf = new ReactiveForm('.reactive')
            expect(rf.$$element).toEqual($('.reactive'))
        })
        it('should find all child input elements', () => {
            let rf = new ReactiveForm('.reactive')
            expect(rf.$inputs.length).toEqual(5)
            expect(rf.$inputs).toEqual($('.reactive').find('input').get())
        })
        it('should create observables from child inputs and merge them', () => {
            spyOn(ReactiveForm.prototype, 'fromInput')
            let rf = new ReactiveForm('.reactive')
            expect(ReactiveForm.prototype.fromInput).toHaveBeenCalledTimes(5)
            expect(rf.stateStream instanceof Observable).toBe(true)
        })
        it('should subscribe to state changes')
    })

    describe('fromInput()', () => {
        it('should accept an input element')
        it('should observe state changes for boolean inputs')
        it('should observe state changes for string inputs')
    })

    describe('state', () => {
        it('should be available on demand')
        it('should update when the form updates')
    })

    describe('onStateChange()', () => {
        it('should get called when state changes')
        it('should receive the state as a parameter')
    })

})