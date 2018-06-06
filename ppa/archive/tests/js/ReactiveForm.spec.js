import { Observable, merge } from 'rxjs'

import ReactiveForm from '../../static/archive/js/ReactiveForm'

describe('Reactive Form', () => {

    beforeAll(() => {
        // create test DOM
        $('body').append('<form class="reactive">\
            <input type="text" name="text" id="text">\
            <input type="number" name="number" id="number">\
            <input type="checkbox" name="checkbox" id="checkbox">\
            <input type="radio" name="radio" value="radio1" id="radio1" checked="">\
            <input type="radio" name="radio" value="radio2" id="radio2">\
        </form>')
    })
    
    describe('constructor()', () => {
        beforeAll(function() {
            spyOn(ReactiveForm, 'fromInput').and.callThrough() // spy on static method
            this.rf = new ReactiveForm('.reactive')
        })
        it('should store the associated form element', function() {
            expect(this.rf.$$element).toEqual($('.reactive'))
        })
        it('should store all child input elements', function() {
            expect(this.rf.$inputs).toEqual($('.reactive').find('input').get())
        })
        it('should create observables from each child input', function() {
            expect(ReactiveForm.fromInput).toHaveBeenCalledTimes(5)
            // expect(ReactiveForm.fromInput).toHaveBeenCalledWith(...$('input').get())
            // it gets called with '0' as the second arg for some reason...why??
        })
        it('should store state as an observable', function() {
            expect(this.rf.stateStream instanceof Observable).toBe(true)
        })
        it('should subscribe to state changes')
    })

    describe('get state', () => {
        it('should be available on demand')
        it('should update when the form updates')
    })

    describe('onStateChange()', () => {
        it('should get called when state changes')
        it('should receive the state as a parameter')
    })

    describe('fromInput()', () => {
        beforeAll(function() {
            let self = this
            $('input').get().map(input => { // for each of the inputs...
                self[input.id] = ReactiveForm.fromInput(input) // define an observable of it at this.inputId
                self[`${input.id}Spy`] = jasmine.createSpy(v => v).and.callThrough() // create a spy for it at this.inputIdSpy
                self[input.id].subscribe(self[`${input.id}Spy`]) // subscribe the spy to the observable
            })
        })
        it('should return an observable', function() {
            $('input').get().map(input => { // for each of the inputs...
                expect(this[input.id] instanceof Observable).toBe(true) // expect that this.inputId is an Observable
            })
        })
        it('should observe state changes for checkboxes', function() {
            $('#checkbox').click() // checked
            expect(this.checkboxSpy).toHaveBeenCalledWith(true)
            $('#checkbox').click() // unchecked
            expect(this.checkboxSpy).toHaveBeenCalledWith(false)
        })
        it('should observe state changes for radios', function() {
            $('#radio2').click() // choose radio option 2
            expect(this.radio2Spy).toHaveBeenCalledWith(true)
            $('#radio1').click() // choose radio option 1
            expect(this.radio1Spy).toHaveBeenCalledWith(true)
        })
        it('should observe state changes for text inputs', function() {
            
        })
    })
})