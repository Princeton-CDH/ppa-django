import { Observable, fromEvent, combineLatest } from 'rxjs'
import 'rxjs/add/operator/pluck'
import 'rxjs/add/operator/map'
import 'rxjs/add/operator/distinctUntilChanged'
import 'rxjs/add/operator/debounceTime'
import 'rxjs/add/operator/startWith'

import DateHistogram from './DateHistogram'

/**
 * Utility function that generates an observable from an <input> tag.
 * Uses document.querySelector to find the input element.
 * Generates an observable sequence of its unique values, with debounce.
 * 
 * @param {string} selector selector for input element
 * @returns Observable
 */
function observableFromInput(selector) {
    let $element = document.querySelector(selector)
    return fromEvent($element, 'input')
        .pluck('target', 'value')
        .startWith($element.value) // makes combineLatest() pick it up immediately
        .debounceTime(500)
        .distinctUntilChanged()
        .map(value => ({
            'element': selector,
            'value': value
        }))
}

export default class ArchiveSearch {
    constructor() {
        /* dom */
        this.$$keywordInput = $('#id_query')
        this.$$titleInput = $('#id_title')
        this.$$authorInput = $('#id_author')
        this.$$minDateInput = $('#id_pub_date_0')
        this.$$maxDateInput = $('#id_pub_date_1')
        this.$$collectionInputs = $('#collections input');
        this.$$minDate = $('.min-date')
        this.$$maxDate = $('.max-date')
        this.$$form = $('.ui.form')
        this.$$sortLinks = $('.sort .item')
        this.$$clearDatesLink = $('.clear-selection')
        this.$$histogram = $('#histogram')
        this.$$checkboxes = $('.ui.checkbox')
        this.$$popup = $('.question-popup')

        /* components */
        this.histogram = new DateHistogram(this.$$histogram)

        /* observables */
        this.inputStream = combineLatest(
            observableFromInput('#id_query'), // keyword
            observableFromInput('#id_title'), // title
            observableFromInput('#id_author'), // author
            observableFromInput('#id_pub_date_0'), // min pub date
            observableFromInput('#id_pub_date_1') // max pub date
        )

        /* bindings */
        this.$$clearDatesLink.click(this.clearDates.bind(this))
        this.$$sortLinks.click(this.onSortChange.bind(this))
        this.$$collectionInputs.change(this.onCollectionChange.bind(this))
        this.inputStream.subscribe(this.submitForm.bind(this))

        /* initialization */
        this.$$checkboxes.checkbox()
        this.$$popup.popup()
        this.render()
    }

    onCollectionChange(event) {
        $(event.target).parent().toggleClass('active')
        this.submitForm()
    }

    onSortChange(event) {
        this.$$sortLinks.find('input[checked=""]').removeAttr('checked')
        this.$$sortLinks.find('input').attr('checked', '')
        this.submitForm()
    }

    updateDates() {
        let minDate = this.$$minDateInput.val()
        let maxDate = this.$$maxDateInput.val()
        // if there's a date set, use it - otherwise use the placeholder
        this.$$minDate.text(minDate != '' ? minDate : this.$$minDateInput.attr('placeholder'))
        this.$$maxDate.text(maxDate != '' ? maxDate : this.$$maxDateInput.attr('placeholder'))
    }
    
    clearDates() {
        this.$$minDateInput.val('')
        this.$$maxDateInput.val('')
        this.submitForm()
    }

    submitForm(formData) {
        // serialize form data to append to GET ajax request
        // make the request
        // parse HTML to get data
        this.render()
    }

    render() {
        this.$$sortLinks.find('input[disabled="disabled"]').parent().addClass('disabled')
        this.updateDates()
        this.histogram.render()
    }
}