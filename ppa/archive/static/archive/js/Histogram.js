import { Subject } from 'rxjs'

export default class Histogram {
    /**
     * Given a CSS selector, treats that element as a histogram visualization and
     * finds a child canvas element on which to draw the histogram. Creates an
     * observable for the underlying data that will redraw when updated. Looks for
     * child elements .min-date and .max-date to show minimum and maximum dates
     * in the data.
     * 
     * @param {any} selector CSS selector
     */
    constructor(selector, options) {
        let self = this
        self.$canvas = $(selector).find('canvas')[0]
        self.$minDisplay = $(selector).find('.min-date')
        self.$maxDisplay = $(selector).find('.max-date')
        self.ctx = this.$canvas.getContext('2d')
        self.dataStream = new Subject()
        self.dataStream.subscribe((data) => self.render.call(self, data))
        options = options || {}  // set default options
        self.backgroundColor = options.backgroundColor || '#efefef'
        self.barColor = options.barColor || '#ccc'
    }

    /**
     * Allows the data to be passed in externally as an object. 
     * 
     * @param {Object} data start, end, and gap values with counts object
     */
    update({ start, end, gap, counts }) {
        this.$minDisplay.text(start)
        this.$maxDisplay.text(end)
        this.dataStream.next(counts)
    }

    /**
     * Receives an updated copy of the data every time data changes and uses
     * it to render the histogram visualization.
     * 
     * @param {Object} counts key-value map of histogram data points
     */
    render(counts) {
        // clear canvas
        this.ctx.clearRect(0, 0, this.$canvas.width, this.$canvas.height)
        // draw background
        this.ctx.fillStyle = this.backgroundColor
        this.ctx.fillRect(0, 0, this.$canvas.width, this.$canvas.height)
        // draw bars
        let i = 0
        let yMax = Math.max(...Object.values(counts))
        let bins = Object.keys(counts).length
        this.ctx.fillStyle = this.barColor
        Object.values(counts).forEach(yVal => {
            let x = Math.floor(i * (this.$canvas.width / bins))
            let y = this.$canvas.height - Math.floor((yVal / yMax) * this.$canvas.height)
            let dx = Math.floor(this.$canvas.width / bins)
            let dy = Math.floor((yVal / yMax) * this.$canvas.height)
            this.ctx.fillRect(x, y, dx, dy)
            i += 1
        })
    }
}