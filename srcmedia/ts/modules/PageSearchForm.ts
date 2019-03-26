import ReactiveForm from './ReactiveForm'
import { KeywordSearch } from './controls'
import ReactiveResults from './ReactiveResults'
import { ajax } from '../../js/modules/Utilities'

class PageSearchForm extends ReactiveForm {
    keyword: KeywordSearch
    results: ReactiveResults

    constructor(element: HTMLFormElement) {
        super(element)
        let query = this.element.elements[0] as HTMLInputElement
        let results = this.element.elements[2] as HTMLOutputElement
        this.keyword = new KeywordSearch(query)
        this.results = new ReactiveResults(results)
    }

    async submit(): Promise<void> {
        await fetch(`${this.target}?${this.serialize()}`, ajax)
            .then(res => res.text())
            .then(html => this.results.update(html))
            .then(() => window.history.pushState(null, 'PPA Archive Search', this.serialize()))
    }

    async update(): Promise<void> {

    }
}

export default PageSearchForm