import { Observable } from 'rxjs'
import ReactiveForm from '../../static/archive/js/ReactiveForm'

jasmine.getFixtures().fixturesPath = 'base/ppa/archive/fixtures/'

describe('Reactive Form', () => {
    
    describe('constructor()', () => {

        beforeEach(function() {
            loadFixtures('form.html')
            this.rf = new ReactiveForm('#form')
        })

        it('should store the associated form element', function() {
            expect(this.rf.$$element).toEqual($('#form'))
        })

        it('should store all child input elements', function() {
            expect(this.rf.$inputs).toEqual($('#form').find('input').get())
        })

        it('should create observables from each child input', function() {
            spyOn(ReactiveForm, 'fromInput').and.callThrough() // spy on static method
            new ReactiveForm('#form')
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

        beforeEach(function() {
            loadFixtures('form.html')
            this.rf = new ReactiveForm('#form')
            this.initialState = $('#form').serializeArray()
        })

        it('should be available on demand', function() {
            // console.log($('body').html())
            expect(this.rf.state).toEqual(this.initialState)
        })

        it('should update when the form updates', function() {
            $('#checkbox').click()
            expect(this.rf.state.filter(el => el.name == 'checkbox')[0].value).toBe('on')
        })
    })

    describe('onStateChange()', () => {
        it('should get called when state changes')
        it('should receive the state as a parameter')
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

        it('should observe state changes for text inputs', function(done) {
            $('#text').val('hello') // change the text
            $('#text')[0].dispatchEvent(new Event('input')) // fake an input event
            setTimeout(() => { // have to wait for the event to be picked up
                expect(this.textSpy).toHaveBeenCalledWith('hello')
                done()
            }, 500) // this comes from .debounceTime(500) on the method
        })

        it('should ignore repeated values for text inputs', function(done) {
            $('#text').val('hello')
            $('#text')[0].dispatchEvent(new Event('input'))
            $('#text')[0].dispatchEvent(new Event('input'))
            $('#text')[0].dispatchEvent(new Event('input'))
            setTimeout(() => {
                expect(this.textSpy).toHaveBeenCalledTimes(1)
                done()
            }, 500)
        })

        it('should observe state changes for number inputs', function(done) {
            $('#number').val('1990') // int would be cast to str anyway
            $('#number')[0].dispatchEvent(new Event('input'))
            setTimeout(() => {
                expect(this.numberSpy).toHaveBeenCalledWith('1990')
                done()
            }, 500)
        })

        it('should ignore repeated values for number inputs', function(done) {
            $('#number').val('1990')
            $('#number')[0].dispatchEvent(new Event('input'))
            $('#number')[0].dispatchEvent(new Event('input'))
            $('#number')[0].dispatchEvent(new Event('input'))
            setTimeout(() => {
                expect(this.numberSpy).toHaveBeenCalledTimes(1)
                done()
            }, 500)
        })
    })
})