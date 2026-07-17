import HistogramController from './histogram_controller'
import { makeController } from './__test_utils__'

const mockCtx = {
    clearRect: jest.fn(),
    fillRect: jest.fn(),
    fillStyle: '',
}

describe('HistogramController', () => {
    let element, canvas, minDate, maxDate

    beforeEach(() => {
        jest.clearAllMocks()
        document.body.innerHTML = `
            <div data-controller="histogram">
                <canvas width="600" height="60"></canvas>
                <span class="min-date"></span>
                <span class="max-date"></span>
            </div>`
        element = document.querySelector('[data-controller="histogram"]')
        canvas = document.querySelector('canvas')
        minDate = document.querySelector('.min-date')
        maxDate = document.querySelector('.max-date')

        // jsdom does not implement canvas getContext — wire it before connect()
        canvas.getContext = jest.fn().mockReturnValue(mockCtx)
    })

    function make() {
        return makeController(HistogramController, element,
            { canvas, minDate, maxDate },
            { barColor: '#ccc', backgroundColor: '#efefef' }
        )
    }

    test('connect() calls getContext("2d") on the canvas', () => {
        make()
        expect(canvas.getContext).toHaveBeenCalledWith('2d')
    })

    test('update() sets minDate text content', () => {
        const ctrl = make()
        ctrl.update({ start: 1800, end: 1900, gap: 10, counts: {} })
        expect(minDate.textContent).toBe('1800')
    })

    test('update() sets maxDate text content', () => {
        const ctrl = make()
        ctrl.update({ start: 1800, end: 1900, gap: 10, counts: {} })
        expect(maxDate.textContent).toBe('1900')
    })

    test('update() triggers canvas clearRect and fillRect via RxJS Subject', done => {
        const ctrl = make()
        ctrl._dataStream.subscribe(() => {
            expect(mockCtx.clearRect).toHaveBeenCalled()
            expect(mockCtx.fillRect).toHaveBeenCalled() // at minimum the background fill
            done()
        })
        ctrl.update({ start: 1800, end: 1900, gap: 10, counts: { '1800': 5, '1810': 10 } })
    })

    test('empty counts renders background fill only (no bars)', done => {
        const ctrl = make()
        ctrl._dataStream.subscribe(() => {
            // clearRect once, fillRect once (background), no bar fills
            expect(mockCtx.fillRect).toHaveBeenCalledTimes(1)
            done()
        })
        ctrl.update({ start: 1800, end: 1900, gap: 10, counts: {} })
    })

    test('disconnect() unsubscribes; update() after disconnect does not throw', () => {
        const ctrl = make()
        ctrl.disconnect()
        expect(() => ctrl.update({ start: 1800, end: 1900, gap: 10, counts: {} })).not.toThrow()
    })
})
