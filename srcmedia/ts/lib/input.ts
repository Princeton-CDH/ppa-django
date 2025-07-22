import { fromEvent, Subject } from 'rxjs'
import { map, debounceTime, distinctUntilChanged } from 'rxjs/operators'

import { Component, Reactive } from './common'

interface RxInputState { // basic state common to all <input> types
    value: string
    name: string
}


interface RxTextInputState extends RxInputState { // no special fields
}

interface RxCheckboxInputState extends RxInputState {
    checked: boolean
}

/**
 * An ancestor for all reactive <input> elements. These elements should always
 * have a `type` attribute, so the class is abstract.
 *
 * The update() method has a default implementation that updates the `value` and
 * `name` attributes; simple types of <input> may not need to override it.
 *
 * @abstract
 * @class RxInput
 * @extends {Component}
 * @implements {Reactive<RxInputState>}
 */
abstract class RxInput extends Component implements Reactive<RxInputState> {
    declare element: HTMLInputElement
    state: Subject<RxInputState>

    constructor(element: HTMLInputElement) {
        super(element)
        this.state = new Subject()
        this.update = this.update.bind(this) // callers need access to `this`
    }

    /**
     * Update state and propagate changes to the <input> element.
     *
     * @param {RxInputState} state
     * @returns {Promise<void>}
     * @memberof RxInput
     */
    async update(newState: Partial<RxInputState>): Promise<void> {
        if (newState.value) this.element.value = newState.value
        if (newState.name) this.element.name = newState.name
        this.state.next({
            value: this.element.value,
            name: this.element.name
        })
    }
}

/**
 * A reactive <input type="text"> element.
 *
 * @class RxTextInput
 * @extends {RxInput}
 * @implements {Reactive<RxTextInputState>}
 */
class RxTextInput extends RxInput implements Reactive<RxTextInputState> {
    declare state: Subject<RxTextInputState>

    constructor(element: HTMLInputElement) {
        super(element)
        // Update state when the user types in a new value, with debounce
        fromEvent(this.element, 'input').pipe(
            map(() => ({ value: this.element.value })),
            debounceTime(750),
            distinctUntilChanged()
        ).subscribe(this.update)
    }
}

/**
 * A reactive <input type="checkbox"> element.
 *
 * @class RxCheckboxInput
 * @extends {RxInput}
 * @implements {Reactive<RxCheckboxInputState>}
 */
class RxCheckboxInput extends RxInput implements Reactive<RxCheckboxInputState>{
    declare state: Subject<RxCheckboxInputState>

    constructor(element: HTMLInputElement) {
        super(element)
        // Update state immediately when the checkbox is clicked
        fromEvent(this.element, 'change').pipe(
            map(() => ({ checked: this.element.checked })),
        ).subscribe(this.update)
    }

    /**
     * Update state and propagate changes to the checkbox element.
     *
     * @param {RxCheckboxInputState} state
     * @returns {Promise<void>}
     * @memberof RxCheckboxInput
     */
    async update(newState: Partial<RxCheckboxInputState>): Promise<void> {
        if (newState.value) this.element.value = newState.value
        if (newState.name) this.element.name = newState.name
        if (newState.checked) this.element.checked = newState.checked
        this.state.next({
            value: this.element.value,
            name: this.element.name,
            checked: this.element.checked
        })
    }
}

export {
    RxInput,
    RxCheckboxInput,
    RxTextInput
}