import { Observable } from 'rxjs'
import ReactiveForm from '../../js/modules/ReactiveForm'

jasmine.getFixtures().fixturesPath = 'base/srcmedia/test/fixtures/'

describe('Reactive Form', () => {

    describe('constructor()', () => {

        beforeEach(function() {
            loadFixtures('form.html')
            this.rf = new ReactiveForm('#form')
            this.$inputs = $('#form').find('input').get()
            this.$selects = $('#form').find('select').get()
            this.$elements = this.$inputs.concat(this.$selects)
        })

        it('should store the associated form element', function() {
            expect(this.rf.$$element).toEqual($('#form'))
        })

        it('should store all child input elements', function() {
            expect(this.rf.$inputs).toContain(this.$inputs)
        })

        it('should store all child select elements', function() {
            expect(this.rf.$inputs).toContain(this.$selects)
        })

        it('should create observables from each child input', function() {
            spyOn(ReactiveForm, 'fromInput').and.callThrough() // spy on static method
            new ReactiveForm('#form') // initialize a new one so constructor is called
            for (let $element of this.$elements) { // check that each input was passed as an arg
                expect(ReactiveForm.fromInput.calls.mostRecent().args[2]).toContain($element)
                // TODO why is the array of inputs the third arg...? why is arg two '0'? ¯\_(ツ)_/¯
            }
        })

        it('should merge input and store as an observable', function() {
            expect(this.rf.inputStream instanceof Observable).toBe(true)
        })

        it('should store state as an observable', function() {
            expect(this.rf.stateStream instanceof Observable).toBe(true)
        })
    })

    describe('get state', () => {

        beforeEach(function() {
            loadFixtures('form.html')
            this.rf = new ReactiveForm('#form')
            this.initialState = $('#form').serializeArray()
        })

        it('should be available on demand', function() {
            expect(this.rf.state).toEqual(this.initialState)
        })

        it('should update when the form updates', function() {
            $('#checkbox').trigger('click') // click it and request its state via the getter
            expect(this.rf.state.filter(el => el.name == 'checkbox')[0].value).toBe('on')
        })
    })

    describe('onStateChange()', () => {

        beforeEach(function() {
            loadFixtures('form.html')
            this.rf = new ReactiveForm('#form')
            this.onStateChangeSpy = jasmine.createSpy().and.callThrough() // create a spy to subscribe to state changes
            this.rf.onStateChange(this.onStateChangeSpy) // subscribe it
            this.initialState = $('#form').serializeArray()
        })

        it('should get called when state changes', function(done) {
            $('#checkbox').trigger('click') // make a change
            expect(this.onStateChangeSpy).toHaveBeenCalledTimes(1)
            $('#text').val('hello') // make another change
            $('#text')[0].dispatchEvent(new Event('input')) // fake the input event
            setTimeout(() => { // have to wait for the event to be picked up
                expect(this.onStateChangeSpy).toHaveBeenCalledTimes(2)
                done()
            }, 850) // this comes from .debounceTime(750) on fromInput()
        })

        it('should receive the state as a parameter', function() {
            $('#checkbox').trigger('click') // new state will create a new object in the state array
            for (let field of this.initialState) { // all original fields should still be in state
                expect(this.onStateChangeSpy.calls.mostRecent().args[0]).toContain(field) // ugly but necessary...
            } // new checkbox state should also be in state
            expect(this.onStateChangeSpy.calls.mostRecent().args[0]).toContain({ name: 'checkbox', value: 'on' })
        })
    })

    describe('fromInput()', () => {

        beforeEach(function() {
            let self = this
            loadFixtures('form.html')
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
            $('#checkbox').trigger('click') // checked
            expect(this.checkboxSpy).toHaveBeenCalledWith(true)
            $('#checkbox').trigger('click') // unchecked
            expect(this.checkboxSpy).toHaveBeenCalledWith(false)
        })

        it('should observe state changes for radios', function() {
            $('#radio2').trigger('click') // choose radio option 2
            expect(this.radio2Spy).toHaveBeenCalledWith(true)
            $('#radio1').trigger('click') // choose radio option 1
            expect(this.radio1Spy).toHaveBeenCalledWith(true)
        })

        it('should observe state changes for text inputs', function(done) {
            $('#text').val('hello')
            $('#text')[0].dispatchEvent(new Event('input'))  // fake the input event
            setTimeout(() => {  // have to wait for the event to be picked up
                expect(this.textSpy).toHaveBeenCalledWith('hello')
                done()
            }, 850)  // this comes from .debounceTime(750) on the method, + buffer
        })

        it('should ignore repeated values for text inputs', function(done) {
            $('#text').val('hello')
            $('#text')[0].dispatchEvent(new Event('input'))
            $('#text')[0].dispatchEvent(new Event('input'))
            $('#text')[0].dispatchEvent(new Event('input'))
            setTimeout(() => {
                expect(this.textSpy).toHaveBeenCalledTimes(1)
                done()
            }, 850)
        })

        it('should observe state changes for number inputs', function(done) {
            $('#number').val('1990') // int would be cast to str anyway
            $('#number')[0].dispatchEvent(new Event('input'))
            setTimeout(() => {
                expect(this.numberSpy).toHaveBeenCalledWith('1990')
                done()
            }, 850)
        })

        it('should ignore repeated values for number inputs', function(done) {
            $('#number').val('1990')
            $('#number')[0].dispatchEvent(new Event('input'))
            $('#number')[0].dispatchEvent(new Event('input'))
            $('#number')[0].dispatchEvent(new Event('input'))
            setTimeout(() => {
                expect(this.numberSpy).toHaveBeenCalledTimes(1)
                done()
            }, 850)
        })
    })
})
