import { Subject } from 'rxjs'

import { Reactive } from '../lib/common'
import { RxForm, RxFormState } from '../lib/form'
import { RxTextInput } from '../lib/input'
import { RxOutput } from '../lib/output'
import { ajax } from '../../js/modules/Utilities'

interface PageSearchFormState extends RxFormState {
    results: string
}

class PageSearchForm extends RxForm implements Reactive<PageSearchFormState>{
    keywordInput: RxTextInput
    resultsOutput: RxOutput
    state: Subject<PageSearchFormState>

    constructor(element: HTMLFormElement) {
        super(element)
        this.state = new Subject()
        // Create reactive components for form controls
        let query = this.element.elements[0] as HTMLInputElement
        let results = this.element.elements[2] as HTMLOutputElement
        this.keywordInput = new RxTextInput(query)
        this.resultsOutput = new RxOutput(results)
        // Submit the form when the keyword input changes
        this.keywordInput.state.subscribe(this.submit.bind(this))
    }

    /**
     * Serialize the form and submit it as a GET request to the form's endpoint,
     * passing the response to update().
     * 
     * Also updates the browser history, saving the search.
     *
     * @returns {Promise<void>}
     * @memberof PageSearchForm
     */
    async submit(): Promise<void> {
        await fetch(`${this.target}?${this.serialize()}`, ajax)
            .then(res => res.text())
            .then(html => this.update({ results: html }))
            .then(() => window.history.pushState(null, 'PPA Archive Search', this.serialize()))
    }

    /**
     * Propagate state changes to the form's elements.
     *
     * @param {PageSearchFormState} state
     * @returns {Promise<void>}
     * @memberof PageSearchForm
     */
    async update(state: PageSearchFormState): Promise<void> {
        return this.resultsOutput.update(state.results) // pass new results to the output
    }
}

export {
    PageSearchForm,
    PageSearchFormState
}

export default PageSearchForm