import { fromEvent, merge } from 'rxjs'
import 'rxjs/add/operator/pluck'
import 'rxjs/add/operator/map'
import 'rxjs/add/operator/distinctUntilChanged'
import 'rxjs/add/operator/debounceTime'


export default class ReactiveForm {
    /**
     * Utility function that creates an observable from elements that emit the
     * "input" event type. (<input>, <select>).
     * 
     * Generates a sequence of values depending on the element type.
     * 
     * @param {HTMLElement} $element <input> element
     * @return {Observable} sequence of values of the element
     */
    static fromInput($element) {
        let observable = fromEvent($element, 'input') // create an observable from the input event
        switch($element.type) { // decide what we need to monitor to determine if there was a change
            case 'checkbox':
            case 'radio':
                return observable.pluck('target', 'checked') // returns boolean immediately
            case 'select':
                return observable.pluck('target', 'value') // return string immediately
            case 'text':
            case 'number':
            default:
                return observable.pluck('target', 'value') // returns string
                    .debounceTime(500) // filter out fast repetitive events
                    .distinctUntilChanged() // filter out non-changes
        }
    }

    /**
     * Given a CSS selector, treats that element as a form and finds all child
     * input elements that belong to that form. Creates an observable for all
     * input changes, and maps it to output a representation of form state.
     * 
     * @param {String} selector CSS selector
     */
    constructor(selector) {
        let self = this
        self.$$element = $(selector)
        self.$inputs = self.$$element.find('input').get() // find child <input> elements
        self.$inputs.push(...self.$$element.find('select').get()) // also add any <select> elements
        self.inputStream = merge(...self.$inputs.map(ReactiveForm.fromInput)) // create and then merge an array of input observables
        self.stateStream = self.inputStream.map(() => self.$$element.serializeArray()) // get the form state each time input state changes
    }

    /**
     * Allows the state to be requested synchronously on demand.
     * 
     * @return {Array} form values as output by jQuery's serializeArray()
     */
    get state() {
        return this.$$element.serializeArray()
    }

    /**
     * Takes a function to subscribe to state changes. The passed function will
     * receive an array representation of form state every time the form is
     * updated.
     * 
     * @param {Function} fn function to subscribe
     * @return {Subscription} handle for subscription
     */
    onStateChange(fn) {
        return this.stateStream.subscribe(fn)
    }
}