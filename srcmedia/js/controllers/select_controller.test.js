import SelectController from './select_controller'
import { makeController } from './__test_utils__'

describe('SelectController', () => {
    let element, select, container, label

    beforeEach(() => {
        document.body.innerHTML = `
            <div>
                <div data-select-target="container" data-value="">
                    <select data-select-target="input">
                        <option value="title_asc" selected>Title A-Z</option>
                        <option value="relevance">Relevance</option>
                    </select>
                    <span class="select-label">Title A-Z</span>
                </div>
            </div>`
        element = document.querySelector('div')
        select = document.querySelector('select')
        container = document.querySelector('[data-select-target="container"]')
        label = document.querySelector('.select-label')
    })

    test('connect() syncs container data-value to selected option', () => {
        makeController(SelectController, element, { input: select, container })
        expect(container.dataset.value).toBe('title_asc')
    })

    test('connect() syncs .select-label text to selected option', () => {
        makeController(SelectController, element, { input: select, container })
        expect(label.textContent).toBe('Title A-Z')
    })

    test('onChange() updates label when selection changes', () => {
        const ctrl = makeController(SelectController, element, { input: select, container })
        select.value = 'relevance'
        ctrl.onChange()
        expect(label.textContent).toBe('Relevance')
    })

    test('onChange() updates container data-value', () => {
        const ctrl = makeController(SelectController, element, { input: select, container })
        select.value = 'relevance'
        ctrl.onChange()
        expect(container.dataset.value).toBe('relevance')
    })

    test('onChange() dispatches a bubbling input event', () => {
        const ctrl = makeController(SelectController, element, { input: select, container })
        const spy = jest.fn()
        element.addEventListener('input', spy)
        select.value = 'relevance'
        ctrl.onChange()
        expect(spy).toHaveBeenCalledTimes(1)
        expect(spy.mock.calls[0][0].bubbles).toBe(true)
    })

    test('setValue() changes the select value and updates label', () => {
        const ctrl = makeController(SelectController, element, { input: select, container })
        ctrl.setValue('relevance')
        expect(select.value).toBe('relevance')
        expect(label.textContent).toBe('Relevance')
    })

    test('setValue() dispatches a bubbling input event', () => {
        const ctrl = makeController(SelectController, element, { input: select, container })
        const spy = jest.fn()
        element.addEventListener('input', spy)
        ctrl.setValue('relevance')
        expect(spy).toHaveBeenCalledTimes(1)
    })

    test('setValue() is a no-op when value is already selected', () => {
        const ctrl = makeController(SelectController, element, { input: select, container })
        const spy = jest.fn()
        element.addEventListener('input', spy)
        ctrl.setValue('title_asc') // already selected
        expect(spy).not.toHaveBeenCalled()
    })
})
