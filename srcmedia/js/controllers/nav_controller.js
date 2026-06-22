import { Controller } from '@hotwired/stimulus'

export default class NavController extends Controller {
    static targets = ['menu', 'toggle']

    connect() {
        this._lastScrollY = window.scrollY
        this._onScroll = this._handleScroll.bind(this)
        window.addEventListener('scroll', this._onScroll, { passive: true })
    }

    disconnect() {
        window.removeEventListener('scroll', this._onScroll)
    }

    toggle() {
        this.menuTarget.classList.toggle('open')
    }

    _handleScroll() {
        const currentScrollY = window.scrollY
        if (currentScrollY > this._lastScrollY && currentScrollY > 100) {
            this.element.classList.add('hidden')
        } else {
            this.element.classList.remove('hidden')
        }
        this._lastScrollY = currentScrollY
    }
}
