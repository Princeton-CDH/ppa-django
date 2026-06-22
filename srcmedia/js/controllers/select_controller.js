import { Controller } from '@hotwired/stimulus'

/**
 * Select controller — replaces Fomantic UI .dropdown() jQuery plugin for the
 * sort dropdown. Wraps a native <select> element with custom styling while
 * keeping full keyboard and screen-reader accessibility.
 *
 * Usage:
 *   <div data-controller="select"
 *        data-select-target="container">
 *     <select data-select-target="input"
 *             data-action="change->select#onChange">
 *       <option value="title_asc">Title A-Z</option>
 *       ...
 *     </select>
 *   </div>
 *
 * The controller dispatches a native "input" event on the hidden sort input
 * whenever the value changes, preserving the existing SearchController logic.
 */
export default class SelectController extends Controller {
    static targets = ['input', 'container']

    connect() {
        this._syncLabel()
    }

    onChange() {
        this._syncLabel()
        // Dispatch input event so SearchController reacts via its RxJS stream
        this.inputTarget.dispatchEvent(new Event('input', { bubbles: true }))
    }

    /**
     * Called by SearchController._setDropdownValue() to programmatically
     * change the selected value (e.g. switching to relevance sort).
     */
    setValue(value) {
        const select = this.inputTarget
        if (select.value === value) return
        select.value = value
        this._syncLabel()
        select.dispatchEvent(new Event('input', { bubbles: true }))
    }

    _syncLabel() {
        const select = this.inputTarget
        const chosen = select.options[select.selectedIndex]
        if (!chosen) return

        const label = this.element.querySelector('.select-label')
        if (label) label.textContent = chosen.text

        // Keep disabled state in sync on the container
        if (this.hasContainerTarget) {
            this.containerTarget.dataset.value = select.value
        }
    }
}
