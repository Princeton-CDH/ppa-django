import { fromEvent, Observable } from 'rxjs'
import { map, debounceTime, distinctUntilChanged } from 'rxjs/operators'
import { Reactive } from './common'

interface Props {
    value: string
}

class KeywordSearch extends Reactive<Props> {
    element: HTMLInputElement
    state: Observable<string>

    constructor(element: HTMLInputElement) {
        super(element)
        this.state = fromEvent(this.element, 'input').pipe(
            map(() => this.element.value),
            debounceTime(500),
            distinctUntilChanged()
        )
        this.state.subscribe(this.emit.bind(this))
    }

    emit(): void {
        this.element.dispatchEvent(new Event('update', { bubbles: true }))
    }

    async update(props: Props): Promise<void> {
        this.element.value = props.value
    }
}

export {
    KeywordSearch
}