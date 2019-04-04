import { Subject } from 'rxjs'

import { Reactive, Component } from './common'

interface RxFormState {
    // eventually this could include generic things like validity
}

class RxForm extends Component implements Reactive<RxFormState> {
    element: HTMLFormElement
    state: Subject<RxFormState>
    target: string

    constructor(element: HTMLFormElement) {
        super(element)
        this.state = new Subject()
        // FIXME naively assuming that the form targets the current path
        this.target = window.location.pathname
    }
    /**
     * Update the form's state. We don't need to change the DOM, so all we do
     * is call next().
     *
     * @param {RxFormState} state
     * @returns {Promise<void>}
     * @memberof RxForm
     */
    async update(state: RxFormState): Promise<void> {
        this.state.next(state)
    }
    /**
     * Serializes the form's state for appending to a URL querystring.
     *
     * @returns {string}
     * @memberof ReactiveForm
     */
    serialize(): string {
        let data = new FormData(this.element)
        let output: { [key: string]: any } = {}
        for (let pair of data.entries()) {
            output[pair[0]] = pair[1]
        }
        return new URLSearchParams(output).toString()
    }
    /**
     * Resets the form to its initial state by calling the native reset() hook.
     *
     * @returns {void}
     * @memberof ReactiveForm
     */
    reset(): void {
        return this.element.reset()
    }
}

export {
    RxForm,
    RxFormState,
}