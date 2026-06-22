import { Controller } from '@hotwired/stimulus'

export default class ClearableController extends Controller {
    static targets = ['input', 'button']

    connect() {
        this._update()
    }

    clear() {
        this.inputTarget.value = ''
        this.inputTarget.focus()
        this._update()
        this.inputTarget.dispatchEvent(new Event('input', { bubbles: true }))
    }

    update() {
        this._update()
    }

    _update() {
        const hasValue = this.inputTarget.value.length > 0
        if (this.hasButtonTarget) {
            this.buttonTarget.style.display = hasValue ? '' : 'none'
        }
    }
}
