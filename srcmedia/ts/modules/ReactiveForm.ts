import { Reactive } from './common'

interface Props {
    sort: any
}

abstract class ReactiveForm extends Reactive<Props> {
    element: HTMLFormElement
    target: string

    constructor(element: HTMLFormElement) {
        super(element)
        this.target = new URL(window.location.href).pathname
        this.element.addEventListener('update', this.submit.bind(this), false)
    }
    /**
     * Submits the form by making an asynchronous GET request to the form's
     * target.
     *
     * @returns {Promise<Response>}
     * @memberof ReactiveForm
     */
    abstract async submit(): Promise<any>
    /**
     * Serializes the form's state for appending to a URL querystring.
     *
     * @returns {string}
     * @memberof ReactiveForm
     */
    serialize(): string {
        return $.param(this.data)
        // return new URLSearchParams(this.data).toString()
    }
    /**
     * Resets the form to its initial state.
     *
     * @returns {void}
     * @memberof ReactiveForm
     */
    reset(): void {
        return this.element.reset()
    }
    /**
     * Returns the state of the form as a object, similar to jQuery's
     * serializeArray().
     *
     * @readonly
     * @type {object}
     * @memberof ReactiveForm
     */
    get data(): object {
        let data = new FormData(this.element)
        let output: { [key: string]: any } = {}
        for (let pair of data.entries()) {
            output[pair[0]] = pair[1]
        }
        return output
    }
}

export default ReactiveForm