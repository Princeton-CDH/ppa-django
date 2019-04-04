import { Subject } from 'rxjs'

import { Component, Reactive } from '../lib/common'
import { ImageLazyLoader } from '../../js/modules/LazyLoad'

type RxOutputState = string

class RxOutput extends Component implements Reactive<RxOutputState> {
    state: Subject<RxOutputState>

    constructor(element: HTMLOutputElement) {
        super(element)
        this.state = new Subject()
        this.update = this.update.bind(this)
    }

    async update(newState: RxOutputState): Promise<void> {
        this.element.innerHTML = newState // update the results
        let images = Array.from(document.querySelectorAll('img[data-src]'))
        new ImageLazyLoader(images) // rebind lazy load
        this.state.next(newState)
    }
}

export {
    RxOutput
}