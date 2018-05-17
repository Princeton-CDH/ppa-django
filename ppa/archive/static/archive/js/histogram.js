export default class DateHistogram {
    constructor($$element) {
        /* dom */
        this.$canvas = $$element.find('canvas')[0]
        this.$$values = $$element.find('.values')
        
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
        let dates = this.$$values.children('dt').map((i, $el) => $($el).text()).get()
        let counts = this.$$values.children('dd').map((i, $el) => $($el).text()).get()
        // populate data property
        dates.map((date, i) => this.data.set(date, counts[i]))
    }

    render() {
        // clear canvas
        this.ctx.clearRect(0, 0, this.$canvas.width, this.$canvas.height)
        // draw background
        this.ctx.fillStyle = '#efefef'
        this.ctx.fillRect(0, 0, this.$canvas.width, this.$canvas.height)
        // draw bars
        let i = 0
        let maxCount = Math.max(...this.data.values())
        this.ctx.fillStyle = '#ccc'
        this.data.forEach((count, date) => {
            let x = Math.floor(i * (this.$canvas.width / 25))
            let y = this.$canvas.height - Math.floor((count / maxCount) * this.$canvas.height)
            let dx = Math.floor(this.$canvas.width / 25)
            let dy = Math.floor((count / maxCount) * this.$canvas.height)
            this.ctx.fillRect(x, y, dx, dy)
            i += 1
        })
    }
}