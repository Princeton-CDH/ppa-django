import { Subject } from 'rxjs'

export default class Histogram {
    /**
     * Given a CSS selector, treats that element as a histogram visualization and
     * finds a child canvas element on which to draw the histogram. Creates an
     * observable for the underlying data that will redraw when updated.
     * 
     * @param {any} selector CSS selector
     */
    constructor(selector, options) {
        let self = this
        self.$canvas = $(selector).find('canvas')[0]
        self.ctx = this.$canvas.getContext('2d')
        self.dataStream = new Subject()
        self.dataStream.subscribe((data) => self.render.call(self, data))
        options = options || {}  // set default options
        self.backgroundColor = options.backgroundColor || '#efefef'
        self.barColor = options.barColor || '#ccc'
    }

    /**
     * Allows the data to be passed in externally as an object. Converts the
     * object to a Map and updates the data store with it.
     * 
     * @param {Object} data key-value map of histogram data points
     */
    update(data) {
        let _data = Object.keys(data)
            .reduce((map, key) => map.set(key, data[key]), new Map())
        this.dataStream.next(_data)
    }

    /**
     * Receives an updated copy of the data every time data changes and uses
     * it to render the histogram visualization.
     * 
     * @param {Map} data key-value map of histogram data points
     */
    render(data) {
        // clear canvas
        this.ctx.clearRect(0, 0, this.$canvas.width, this.$canvas.height)
        // draw background
        this.ctx.fillStyle = this.backgroundColor
        this.ctx.fillRect(0, 0, this.$canvas.width, this.$canvas.height)
        // draw bars
        let i = 0
        let yMax = Math.max(...data.values())
        this.ctx.fillStyle = this.barColor
        data.forEach((yVal, xVal) => {
            let x = Math.floor(i * (this.$canvas.width / data.size))
            let y = this.$canvas.height - Math.floor((yVal / yMax) * this.$canvas.height)
            let dx = Math.floor(this.$canvas.width / data.size)
            let dy = Math.floor((yVal / yMax) * this.$canvas.height)
            this.ctx.fillRect(x, y, dx, dy)
            i += 1
        })
    }
}