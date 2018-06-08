import { Subject } from 'rxjs'
import Histogram from '../../static/archive/js/Histogram'

jasmine.getFixtures().fixturesPath = 'base/ppa/archive/fixtures/'

describe('Histogram', () => {

    describe('constructor()', () => {

        beforeEach(function() {
            loadFixtures('histogram.html')
            this.h = new Histogram('#histogram')
        })

        it('should store the associated canvas element', function() {
            expect(this.h.$canvas).toEqual($('#histogram canvas')[0])
        })

        it('should store the canvas context', function() {
            expect(this.h.ctx).toEqual($('#histogram canvas')[0].getContext('2d'))
        })

        it('should store its data as a reactive subject', function() {
            expect(this.h.dataStream instanceof Subject).toBe(true)
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
            this.testData = { 2006: 5, 2007: 4, 2008: 23 } // fake data
            spyOn(this.h, 'update').and.callThrough() // spy on the function itself
            spyOn(this.h, 'render').and.callThrough() // spy on the render() function
            spyOn(this.h.dataStream, 'next').and.callThrough() // spy on the calls to update the data
            this.h.update(this.testData) // pass in some data
        })

        it('should update the data property', function() {
            expect(this.h.dataStream.next).toHaveBeenCalled()
        })

        it('should convert the passed object to a Map', function() {
            expect(this.h.dataStream.next).toHaveBeenCalledWith(jasmine.any(Map)) // should be map
            // for (let prop in this.testData) { // test that the Map has all the same keys/vals as the object
                // expect(this.h.dataStream.next.calls.mostRecent().args[0].get(prop)).toEqual(this.testData.prop)
                // TODO fails because the Map is still undefined...why?
            // }
        })

        it('should trigger render()', function() {
            expect(this.h.render).toHaveBeenCalledWith(jasmine.any(Map))
        })
    })

    describe('render()', () => {

        beforeEach(function() {
            loadFixtures('histogram.html')
            this.h = new Histogram('#histogram')
            this.testDataMap = new Map([[2006, 5], [2007, 4], [2008, 23]])
            spyOn(this.h.ctx, 'clearRect').and.callThrough() // spy on the clear canvas func
            spyOn(this.h.ctx, 'fillRect').and.callThrough() // spy on the bar drawing func
            this.h.render(this.testDataMap) // manually pass data to render()
        })

        it('should clear the canvas', function() {
            expect(this.h.ctx.clearRect).toHaveBeenCalled()
        })

        it('should draw a bar for each data point', function() {
            // one call for filling the background of the histogram, then one per bar
            expect(this.h.ctx.fillRect).toHaveBeenCalledTimes(this.testDataMap.size + 1)
        })
    })
})