import { Controller } from '@hotwired/stimulus'

/**
 * Keyboard navigation for the About dropdown menu.
 * Replaces modules/NavMenu.js (AboutNav class).
 *
 * Expected HTML structure:
 *   <div data-controller="about-nav">
 *     <div data-about-nav-target="text" tabindex="0">About</div>
 *     <div class="menu">
 *       <div class="item"><a href="...">Page</a></div>
 *       ...
 *     </div>
 *   </div>
 */
export default class AboutNavController extends Controller {
    static targets = ['text']

    connect() {
        this.element.addEventListener('focusin', this._onFocusIn)
        this.element.addEventListener('focusout', this._onFocusOut)
        this.element.addEventListener('keydown', this._onKeyDown)
    }

    disconnect() {
        this.element.removeEventListener('focusin', this._onFocusIn)
        this.element.removeEventListener('focusout', this._onFocusOut)
        this.element.removeEventListener('keydown', this._onKeyDown)
    }

    // Make the Semantic UI dropdown appear on keyboard focus
    _onFocusIn = () => {
        this.element.classList.add('hovered')
    }

    _onFocusOut = () => {
        this.element.classList.remove('hovered')
    }

    _onKeyDown = (ev) => {
        const code = ev.code || (ev.originalEvent && ev.originalEvent.code)

        if (code === 'ArrowDown') {
            ev.preventDefault()
            if (ev.target.nodeName === 'A') {
                // Move to next item's link
                const nextLink = ev.target.closest('.item')?.nextElementSibling?.querySelector('a')
                nextLink?.focus()
            } else {
                // From the "About" text, focus the first menu link
                this.element.querySelector('.menu .item a')?.focus()
            }
        }

        if (code === 'ArrowUp') {
            ev.preventDefault()
            if (ev.target.nodeName === 'A') {
                const prevLink = ev.target.closest('.item')?.previousElementSibling?.querySelector('a')
                if (prevLink) {
                    prevLink.focus()
                } else {
                    // Back to the "About" text trigger
                    this.textTarget?.focus()
                }
            }
        }
    }
}
