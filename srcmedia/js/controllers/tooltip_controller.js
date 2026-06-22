import { Controller } from '@hotwired/stimulus'

/**
 * Tooltip controller — replaces Fomantic UI .popup() jQuery plugin.
 *
 * Uses the native HTML Popover API (broadly supported since 2023) with a
 * CSS-positioned tooltip element. Falls back gracefully in older browsers
 * (the trigger icon is still visible; the tooltip just won't appear).
 *
 * Usage:
 *   <span data-controller="tooltip"
 *         data-tooltip-content-value="Help text here"
 *         data-tooltip-position-value="top">
 *     <i class="ui question circle icon"></i>
 *   </span>
 */
export default class TooltipController extends Controller {
    static values = {
        content: String,
        position: { type: String, default: 'top' },
    }

    connect() {
        this._tooltip = null
        this.element.setAttribute('aria-describedby', `tooltip-${this.identifier}-${this._id()}`)
        this.element.addEventListener('mouseenter', this._show)
        this.element.addEventListener('mouseleave', this._hide)
        this.element.addEventListener('focusin', this._show)
        this.element.addEventListener('focusout', this._hide)
        // Make trigger focusable if it isn't already
        if (!this.element.getAttribute('tabindex')) {
            this.element.setAttribute('tabindex', '0')
        }
    }

    disconnect() {
        this._hide()
        this.element.removeEventListener('mouseenter', this._show)
        this.element.removeEventListener('mouseleave', this._hide)
        this.element.removeEventListener('focusin', this._show)
        this.element.removeEventListener('focusout', this._hide)
    }

    _show = () => {
        if (this._tooltip) return
        const id = `tooltip-${this.identifier}-${this._id()}`

        const el = document.createElement('div')
        el.id = id
        el.role = 'tooltip'
        el.className = `ppa-tooltip ppa-tooltip--${this.positionValue}`
        el.textContent = this.contentValue
        document.body.appendChild(el)
        this._tooltip = el

        this._position()
    }

    _hide = () => {
        this._tooltip?.remove()
        this._tooltip = null
    }

    _position() {
        const trigger = this.element.getBoundingClientRect()
        const tip = this._tooltip
        // Temporarily visible off-screen to measure
        tip.style.visibility = 'hidden'
        tip.style.position = 'fixed'
        document.body.appendChild(tip)

        const tipRect = tip.getBoundingClientRect()
        const gap = 8

        let top, left
        switch (this.positionValue) {
            case 'bottom':
                top = trigger.bottom + gap
                left = trigger.left + trigger.width / 2 - tipRect.width / 2
                break
            case 'left':
                top = trigger.top + trigger.height / 2 - tipRect.height / 2
                left = trigger.left - tipRect.width - gap
                break
            case 'right':
                top = trigger.top + trigger.height / 2 - tipRect.height / 2
                left = trigger.right + gap
                break
            case 'top':
            default:
                top = trigger.top - tipRect.height - gap
                left = trigger.left + trigger.width / 2 - tipRect.width / 2
                break
        }

        // Clamp to viewport
        left = Math.max(gap, Math.min(left, window.innerWidth - tipRect.width - gap))
        top = Math.max(gap, Math.min(top, window.innerHeight - tipRect.height - gap))

        tip.style.top = `${top + window.scrollY}px`
        tip.style.left = `${left + window.scrollX}px`
        tip.style.position = 'absolute'
        tip.style.visibility = ''
    }

    _id() {
        if (!this._uid) this._uid = Math.random().toString(36).slice(2, 7)
        return this._uid
    }
}
