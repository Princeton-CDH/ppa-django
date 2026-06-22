import { Controller } from '@hotwired/stimulus'

export default class LazyLoadController extends Controller {
    static targets = ['image']

    connect() {
        if ('IntersectionObserver' in window) {
            this._observer = new IntersectionObserver(this._onIntersect.bind(this))
            this.imageTargets.forEach(img => this._observer.observe(img))
        } else {
            // Fallback: load all images immediately
            this.imageTargets.forEach(img => this._loadImage(img))
        }
    }

    disconnect() {
        if (this._observer) {
            this._observer.disconnect()
        }
    }

    _onIntersect(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                this._loadImage(entry.target)
                this._observer.unobserve(entry.target)
            }
        })
    }

    _loadImage(img) {
        const src = img.dataset.src
        if (src) {
            img.src = src
            img.removeAttribute('data-src')
        }
    }
}
