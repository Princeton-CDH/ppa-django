import { Subject } from 'rxjs'
import Histogram from '../../js/modules/Histogram'

jasmine.getFixtures().fixturesPath = 'base/srcmedia/test/fixtures/'

describe('Histogram', () => {

    describe('constructor()', () => {

        beforeEach(function() {
            loadFixtures('histogram.html')
            this.h = new Histogram('#histogram')
        })

        it('should store the associated canvas element', function() {
            expect(this.h.$canvas).toEqual($('#histogram canvas')[0])
        })

        it('should store associated min/max date display elements', function() {
            expect(this.h.$minDisplay).toEqual($('#histogram .min-date')[0])
            expect(this.h.$maxDisplay).toEqual($('#histogram .max-date')[0])
        })

        it('should store the canvas context', function() {
            expect(this.h.ctx).toEqual($('#histogram canvas')[0].getContext('2d'))
        })

        it('should store its data as a reactive subject', function() {
            expect(this.h.dataStream).toBeInstanceOf(Subject)
        })

        it('should accept an options object', function() {
            this.h = new Histogram('#histogram', { // re-initialize with options
                backgroundColor: '#000',
                barColor: '#fff'
            })
            expect(this.h.backgroundColor).toBe('#000')
            expect(this.h.barColor).toBe('#fff')
        })

        it('should set default options', function() {
            expect(this.h.backgroundColor).toBe('#efefef') // default if none passed
            expect(this.h.barColor).toBe('#ccc')
        })
    })

    describe('update()', () => {

        beforeEach(function() {
            loadFixtures('histogram.html')
            this.h = new Histogram('#histogram')
            this.testData = { // fake data
                counts: { '2006': '5', '2007': '4', '2008': '23' },
                start: '2006',
                end: '2009', // mimic different end value
                gap: '1'
            }
            spyOn(this.h, 'update').and.callThrough() // spy on the function itself
            spyOn(this.h, 'render').and.callThrough() // spy on the render() function
            spyOn(this.h.dataStream, 'next').and.callThrough() // spy on the calls to update the data
            this.h.update(this.testData) // pass in some data
        })

        it('should update the data property', function() {
            expect(this.h.dataStream.next).toHaveBeenCalled()
        })

        it('should trigger render()', function() {
            expect(this.h.render).toHaveBeenCalled()
        })

        it('should update min and max values', function() {
            expect(this.h.$minDisplay.text()).toEqual(this.testData.start)
            expect(this.h.$maxDisplay.text()).toEqual(this.testData.end)
        })
    })

    describe('render()', () => {

        beforeEach(function() {
            loadFixtures('histogram.html')
            this.h = new Histogram('#histogram')
            this.counts = { '2006': '5', '2007': '4', '2008': '23' },
            spyOn(this.h.ctx, 'clearRect').and.callThrough() // spy on the clear canvas func
            spyOn(this.h.ctx, 'fillRect').and.callThrough() // spy on the bar drawing func
            this.h.render(this.counts) // manually pass counts to render()
        })

        it('should clear the canvas', function() {
            expect(this.h.ctx.clearRect).toHaveBeenCalled()
        })

        it('should draw a bar for each data point', function() {
            // one call for filling the background of the histogram, then one per bar
            expect(this.h.ctx.fillRect).toHaveBeenCalledTimes(4)
        })
    })
})