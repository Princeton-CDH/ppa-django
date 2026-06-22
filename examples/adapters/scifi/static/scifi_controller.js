/**
 * Stimulus controller for the scifi adapter.
 *
 * Renders a star rating display from a numeric score (0–5).
 *
 * Usage (auto-wired via adapter frontend.js):
 *   <dd class="scifi_rating_score"
 *       data-controller="scifi-rating"
 *       data-scifi-rating-score-value="4.2">
 *     4.2
 *   </dd>
 */
import { Application, Controller } from 'https://unpkg.com/@hotwired/stimulus/dist/stimulus.js'

class ScifiRatingController extends Controller {
    static values = { score: Number }

    connect() {
        const score = this.scoreValue
        if (!score) return
        const stars = this._buildStars(score)
        const label = document.createElement('span')
        label.className = 'rating-label'
        label.textContent = ` ${score.toFixed(1)}`
        label.setAttribute('aria-hidden', 'true')
        this.element.innerHTML = ''
        this.element.appendChild(stars)
        this.element.appendChild(label)
        this.element.setAttribute('aria-label', `Rating: ${score.toFixed(1)} out of 5`)
    }

    _buildStars(score) {
        const wrap = document.createElement('span')
        wrap.className = 'stars'
        wrap.setAttribute('aria-hidden', 'true')
        for (let i = 1; i <= 5; i++) {
            const star = document.createElement('span')
            star.className = 'star'
            if (score >= i) {
                star.textContent = '★'
                star.classList.add('full')
            } else if (score >= i - 0.5) {
                star.textContent = '½'
                star.classList.add('half')
            } else {
                star.textContent = '☆'
                star.classList.add('empty')
            }
            wrap.appendChild(star)
        }
        return wrap
    }
}

const app = Application.start()
app.register('scifi-rating', ScifiRatingController)
