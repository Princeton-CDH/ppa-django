import { Observable, merge } from 'rxjs'

import ReactiveForm from '../../static/archive/js/ReactiveForm'

describe('Reactive Form', () => {

    beforeAll(() => {
        // create test DOM
        $('body').append('<form class="reactive">\
            <input type="text" name="query" id="id_query">\
            <input type="number" name="date">\
            <input type="checkbox" name="bool" id="id_bool">\
            <input type="radio" name="choice" value="optionOne" id="id_option1" checked="">\
            <input type="radio" name="choice" value="optionTwo" id="id_option2">\
        </form>')
    })
    
    describe('constructor()', () => {
        beforeAll(function() {
            spyOn(ReactiveForm, 'fromInput') // spy on static method
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
        })
        it('should store state as an observable', function() {
            expect(this.rf.stateStream instanceof Observable).toBe(true)
        })
        it('should subscribe to state changes')
    })

    describe('fromInput()', () => {
        beforeAll(function() {
            // set up some observables from inputs
            this.checkbox = ReactiveForm.fromInput($('#id_bool').get())
            this.radio1 = ReactiveForm.fromInput($('#id_option1').get())
            this.radio2 = ReactiveForm.fromInput($('#id_option2').get())
            // create some spies to subscribe to the observables
            this.checkboxSpy = jasmine.createSpy(v => v).and.callThrough()
            this.radio1Spy = jasmine.createSpy(v => v).and.callThrough()
            this.radio2Spy = jasmine.createSpy(v => v).and.callThrough()
            // subscribe them
            this.checkbox.subscribe(this.checkboxSpy)
            this.radio1.subscribe(this.radio1Spy)
            this.radio2.subscribe(this.radio2Spy)
        })
        it('should return an observable', function() {
            expect(this.checkbox instanceof Observable).toBe(true)
            expect(this.radio1 instanceof Observable).toBe(true)
            expect(this.radio2 instanceof Observable).toBe(true)
        })
        it('should observe state changes for checkboxes', function() {
            $('#id_bool').click() // checked
            expect(this.checkboxSpy).toHaveBeenCalledWith(true)
            $('#id_bool').click() // unchecked
            expect(this.checkboxSpy).toHaveBeenCalledWith(false)
        })
        it('should observe state changes for radios', function() {
            $('#id_option2').click() // choose radio option 2
            expect(this.radio2Spy).toHaveBeenCalledWith(true)
            $('#id_option1').click() // choose radio option 1
            expect(this.radio1Spy).toHaveBeenCalledWith(true)
            expect(this.radio2Spy).toHaveBeenCalledWith(false)
        })
        it('should observe state changes for string inputs')
    })

    describe('get state', () => {
        it('should be available on demand')
        it('should update when the form updates')
    })

    describe('onStateChange()', () => {
        it('should get called when state changes')
        it('should receive the state as a parameter')
    })

})