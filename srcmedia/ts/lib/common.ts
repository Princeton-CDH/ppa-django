import { Subject } from 'rxjs'

/**
 * Denotes a class that will keep a record of state changes as an observable
 * sequence, and allow that state to be updated externally.
 * 
 * We expect that the update() method will add the new state to the sequence,
 * as well as perform all changes necessary to reflect the new state.
 *
 * @interface Reactive
 * @template State
 */
interface Reactive<State> {
    state: Subject<State>
    update(state: Partial<State>): Promise<any>
}

/**
 * Base class that keeps a reference to an HTMLElement.
 *
 * @class Component
 */
class Component {
    element: HTMLElement

    constructor(element: HTMLElement) {
        this.element = element
    }
}

export {
    Reactive,
    Component
}