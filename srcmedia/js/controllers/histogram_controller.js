import { Controller } from '@hotwired/stimulus'
import { Subject } from 'rxjs'

/**
 * Canvas-based histogram visualization for date range faceting.
 * Replaces modules/Histogram.js.
 *
 * Expected HTML structure:
 *   <div data-controller="histogram"
 *        data-histogram-bar-color-value="#ccc"
 *        data-histogram-background-color-value="#efefef">
 *     <canvas data-histogram-target="canvas" height="60" width="600"></canvas>
 *     <span data-histogram-target="minDate"></span>
 *     <span data-histogram-target="maxDate"></span>
 *   </div>
 */
export default class HistogramController extends Controller {
    static targets = ['canvas', 'minDate', 'maxDate']
    static values = {
        barColor: { type: String, default: '#ccc' },
        backgroundColor: { type: String, default: '#efefef' },
    }

    connect() {
        this._ctx = this.canvasTarget.getContext('2d')
        this._dataStream = new Subject()
        this._subscription = this._dataStream.subscribe(data => this._render(data))
    }

    disconnect() {
        this._subscription?.unsubscribe()
    }

    /**
     * Update histogram with new facet data.
     * Called externally by SearchController when search results change.
     *
     * @param {{ start: number, end: number, gap: number, counts: Object }} data
     */
    update({ start, end, gap, counts }) {
        if (this.hasMinDateTarget) this.minDateTarget.textContent = start
        if (this.hasMaxDateTarget) this.maxDateTarget.textContent = end
        this._dataStream.next(counts)
    }

    _render(counts) {
        const canvas = this.canvasTarget
        const ctx = this._ctx
        const values = Object.values(counts)

        ctx.clearRect(0, 0, canvas.width, canvas.height)

        // background
        ctx.fillStyle = this.backgroundColorValue
        ctx.fillRect(0, 0, canvas.width, canvas.height)

        if (!values.length) return

        // bars
        const yMax = Math.max(...values)
        const bins = values.length
        ctx.fillStyle = this.barColorValue
        values.forEach((yVal, i) => {
            const x = Math.floor(i * (canvas.width / bins))
            const y = canvas.height - Math.floor((yVal / yMax) * canvas.height)
            const dx = Math.floor(canvas.width / bins)
            const dy = Math.floor((yVal / yMax) * canvas.height)
            ctx.fillRect(x, y, dx, dy)
        })
    }
}
