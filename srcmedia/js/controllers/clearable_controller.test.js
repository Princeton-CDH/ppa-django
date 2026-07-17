import ClearableController from './clearable_controller'
import { makeController } from './__test_utils__'

describe('ClearableController', () => {
    let element, input, button

    beforeEach(() => {
        document.body.innerHTML = `
            <div>
                <input data-clearable-target="input" value="">
                <button data-clearable-target="button" style="display:none">✕</button>
            </div>`
        element = document.querySelector('div')
        input = document.querySelector('input')
        button = document.querySelector('button')
    })

    test('hides button on connect when input is empty', () => {
        makeController(ClearableController, element, { input, button })
        expect(button.style.display).toBe('none')
    })

    test('shows button on connect when input has a value', () => {
        input.value = 'hello'
        makeController(ClearableController, element, { input, button })
        expect(button.style.display).toBe('')
    })

    test('clear() empties the input', () => {
        input.value = 'hello'
        const ctrl = makeController(ClearableController, element, { input, button })
        ctrl.clear()
        expect(input.value).toBe('')
    })

    test('clear() hides the button', () => {
        input.value = 'hello'
        const ctrl = makeController(ClearableController, element, { input, button })
        ctrl.clear()
        expect(button.style.display).toBe('none')
    })

    test('clear() dispatches a bubbling input event', () => {
        input.value = 'hello'
        const ctrl = makeController(ClearableController, element, { input, button })
        const spy = jest.fn()
        element.addEventListener('input', spy)
        ctrl.clear()
        expect(spy).toHaveBeenCalledTimes(1)
        expect(spy.mock.calls[0][0].bubbles).toBe(true)
    })

    test('update() shows button when input gains a value', () => {
        const ctrl = makeController(ClearableController, element, { input, button })
        input.value = 'new text'
        ctrl.update()
        expect(button.style.display).toBe('')
    })

    test('update() hides button when input is empty', () => {
        input.value = 'text'
        const ctrl = makeController(ClearableController, element, { input, button })
        input.value = ''
        ctrl.update()
        expect(button.style.display).toBe('none')
    })

    test('does not throw when hasButtonTarget is false', () => {
        const mockScope = { element, identifier: 'test', schema: {} }
        const mockContext = { application: { logFormattedMessage: () => {} }, scope: mockScope }
        const ctrl = new ClearableController(mockContext)
        ctrl.inputTarget = input
        ctrl.hasButtonTarget = false
        expect(() => ctrl.connect()).not.toThrow()
    })
})
