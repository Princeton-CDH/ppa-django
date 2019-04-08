import { Subject } from 'rxjs'

import { Reactive } from '../lib/common'
import { RxForm, RxFormState } from '../lib/form'
import { ajax } from '../../js/modules/Utilities'

interface PageSearchFormState extends RxFormState {
    results: string
}

class PageSearchForm extends RxForm implements Reactive<PageSearchFormState>{
    state: Subject<PageSearchFormState>

    constructor(element: HTMLFormElement) {
        super(element)
        this.state = new Subject()
        this.submit = this.submit.bind(this) // so it can be called externally
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
        return fetch(`${this.target}?${this.serialize()}`, ajax)
            .then(res => res.text())
            .then(html => this.update({ results: html }))
            .then(() => window.history.pushState(null, document.title, `?${this.serialize()}`))
    }
}

export {
    PageSearchForm,
    PageSearchFormState
}

export default PageSearchForm