export default class Histogram {
    constructor(selector) {
        /* dom */
        this.$canvas = $(selector).find('canvas')[0]
        this.$$values = $(selector).find('.values')
        
        /* properties */
        this.ctx = this.$canvas.getContext('2d')
        this.data = new Map()
        
        /* initialization */
        this.getData()
        this.render()
    }

    getData() {
        // clear old data
        this.data.clear()
        // extract data from <dt> and <dd> elements
        let xVals = this.$$values.children('dt').map((i, $el) => $($el).text()).get()
        let yVals = this.$$values.children('dd').map((i, $el) => $($el).text()).get()
        // populate data property
        xVals.map((val, i) => this.data.set(val, yVals[i]))
    }

    render() {
        // clear canvas
        this.ctx.clearRect(0, 0, this.$canvas.width, this.$canvas.height)
        // draw background
        this.ctx.fillStyle = '#efefef'
        this.ctx.fillRect(0, 0, this.$canvas.width, this.$canvas.height)
        // draw bars
        let i = 0
        let yMax = Math.max(...this.data.values())
        this.ctx.fillStyle = '#ccc'
        this.data.forEach((yVal, xVal) => {
            let x = Math.floor(i * (this.$canvas.width / this.data.size))
            let y = this.$canvas.height - Math.floor((yVal / yMax) * this.$canvas.height)
            let dx = Math.floor(this.$canvas.width / this.data.size)
            let dy = Math.floor((yVal / yMax) * this.$canvas.height)
            this.ctx.fillRect(x, y, dx, dy)
            i += 1
        })
    }
}