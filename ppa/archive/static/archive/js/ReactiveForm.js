import { fromEvent, merge } from 'rxjs'
import 'rxjs/add/operator/pluck'
import 'rxjs/add/operator/distinctUntilChanged'
import 'rxjs/add/operator/debounceTime'
import 'rxjs/add/operator/startWith'


export default class ReactiveForm {
    /**
     * Given a CSS selector, treats that element as a form and finds all child
     * input elements that belong to that form. Builds a set of observables
     * using fromInput() and merges them into a single observable for the form,
     * then subscribes to form state changes and calls onStateChange.
     * 
     * @param {String} selector CSS selector
     */
    constructor(selector) {
        let self = this
        self.$$element = $(selector)
        self.$inputs = self.$$element.find('input').get() // find child <input> elements
        self.stateStream = merge(self.$inputs.map(self.fromInput)) // create and then merge an array of input observables
        self.stateStream.subscribe(() => { // subscribe to state changes and pass them to onStateChange()
            self.onStateChange.call(self, self.$$element.serializeArray())
        })
    }

    /**
     * Utility function that creates an observable from an <input> tag.
     * Generates a sequence of values depending on the input type.
     * 
     * @param {HTMLElement} $element <input> element
     * @return {Observable} sequence of values of the element
     */
    fromInput($element) {
        let observable = fromEvent($element, 'input') // create an observable from the input event
        switch($element.type) { // decide what we need to monitor to determine if there was a change
            case 'checkbox':
            case 'radio':
                return observable.pluck('target', 'checked') // returns boolean
            case 'text':
            case 'number':
            default:
                return observable.pluck('target', 'value') // returns string
                    .debounceTime(500) // filter out fast repetitive events
                    .distinctUntilChanged() // filter out non-changes
        }
    }

    /**
     * Allows the state to be requested on demand as an array.
     * 
     * @return {Array} form values as output by jQuery's serializeArray()
     */
    get state() {
        return this.$$element.serializeArray()
    }

    /**
     * Function that receives an array representation of form state every time
     * the form is updated. Can be extended to e.g. make an ajax request, or
     * update the queryString in the URL bar.
     * 
     * @param {Array} state form values as output by jQuery's serializeArray()
     */
    onStateChange(state) {
    }
}