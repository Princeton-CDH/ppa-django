import SearchController from './search_controller'
import { makeController } from './__test_utils__'

// Mock fetch globally
global.fetch = jest.fn()

// Mock sessionStorage
const sessionStorageMock = (() => {
    let store = {}
    return {
        getItem: jest.fn(key => store[key] ?? null),
        setItem: jest.fn((key, val) => { store[key] = val }),
        removeItem: jest.fn(key => { delete store[key] }),
        clear: jest.fn(() => { store = {} }),
    }
})()
Object.defineProperty(window, 'sessionStorage', { value: sessionStorageMock, writable: false })

// Build a minimal DOM with all IDs and targets SearchController needs.
// Collections start pre-checked/active to match real page behaviour (server
// pre-selects all collections on initial load).
function buildDOM() {
    document.body.innerHTML = `
        <div data-controller="search">
            <form data-search-target="form">
                <input type="text" name="query" data-search-target="textInput" value="">
                <div id="collections">
                    <label class="ui button active">
                        <input type="checkbox" name="collections" value="col1" checked>
                        Collection 1
                    </label>
                    <label class="ui button active">
                        <input type="checkbox" name="collections" value="col2" checked>
                        Collection 2
                    </label>
                    <label class="ui button">
                        <input type="checkbox" name="collections" value="col3" disabled>
                        Collection 3 (disabled)
                    </label>
                </div>
                <input type="number" id="id_pub_date_0" value="">
                <input type="number" id="id_pub_date_1" value="">
                <button class="show-advanced">Advanced</button>
                <div class="advanced segment" style="display:none">
                    <input type="text" name="title" class="advanced" value="">
                </div>
                <div class="advanced column" style="display:none"></div>
            </form>
            <span data-search-target="validation" style="visibility:hidden"></span>
            <div data-search-target="results"></div>
            <div data-search-target="workscount"></div>
            <span class="show-advanced search-active" style="display:none"></span>
        </div>`
}

function makeSearchController(extraTargets = {}) {
    const element = document.querySelector('[data-controller="search"]')
    const form = document.querySelector('[data-search-target="form"]')
    const validation = document.querySelector('[data-search-target="validation"]')
    const results = document.querySelector('[data-search-target="results"]')
    const workscount = document.querySelector('[data-search-target="workscount"]')
    const textInputEl = document.querySelector('[data-search-target="textInput"]')

    const mockScope = { element, identifier: 'test', schema: {} }
    const mockContext = { application: { logFormattedMessage: () => {} }, scope: mockScope }
    const ctrl = new SearchController(mockContext)
    ctrl.formTarget = form
    ctrl.hasFormTarget = true
    ctrl.validationTarget = validation
    ctrl.hasValidationTarget = true
    ctrl.resultsTarget = results
    ctrl.hasResultsTarget = true
    ctrl.workscountTarget = workscount
    ctrl.hasWorkscountTarget = true
    ctrl.textInputTargets = [textInputEl]
    ctrl.hasTextInputTarget = true
    ctrl.relevanceOptionTargets = []
    ctrl.hasSortInputTarget = false
    ctrl.hasPaginationTopTarget = false
    ctrl.hasResultsCountTarget = false
    ctrl.hasFacetsTarget = false
    ctrl.hasAdvancedSearchIndicatorTarget = false
    ctrl.hasSortDropdownTarget = false

    Object.assign(ctrl, extraTargets)

    ctrl.connect()
    return ctrl
}

// -------------------------------------------------------------------------
// Date validation
// -------------------------------------------------------------------------
describe('SearchController — date validation', () => {
    beforeEach(() => {
        buildDOM()
        sessionStorageMock.clear()
        jest.clearAllMocks()
    })

    afterEach(() => {
        document.body.innerHTML = ''
    })

    test('returns true when both date fields are empty', () => {
        const ctrl = makeSearchController()
        expect(ctrl._validate()).toBe(true)
    })

    test('returns true when only min is set to a valid value', () => {
        const ctrl = makeSearchController()
        document.getElementById('id_pub_date_0').value = '1800'
        expect(ctrl._validate()).toBe(true)
    })

    test('returns false and shows validation when min > max', () => {
        const ctrl = makeSearchController()
        const validationEl = document.querySelector('[data-search-target="validation"]')
        document.getElementById('id_pub_date_0').value = '1900'
        document.getElementById('id_pub_date_1').value = '1800'
        expect(ctrl._validate()).toBe(false)
        expect(validationEl.style.visibility).toBe('visible')
    })

    test('returns true and hides validation when dates are valid', () => {
        const ctrl = makeSearchController()
        const validationEl = document.querySelector('[data-search-target="validation"]')
        document.getElementById('id_pub_date_0').value = '1800'
        document.getElementById('id_pub_date_1').value = '1900'
        expect(ctrl._validate()).toBe(true)
        expect(validationEl.style.visibility).toBe('hidden')
    })
})

// -------------------------------------------------------------------------
// Advanced search toggle
// -------------------------------------------------------------------------
describe('SearchController — advanced search toggle', () => {
    beforeEach(() => {
        buildDOM()
        sessionStorageMock.clear()
        jest.clearAllMocks()
    })

    afterEach(() => {
        document.body.innerHTML = ''
    })

    test('toggleAdvancedSearch() shows .advanced elements when hidden', () => {
        const ctrl = makeSearchController()
        ctrl.toggleAdvancedSearch()
        const segments = document.querySelectorAll('.advanced.segment')
        expect(segments[0].style.display).toBe('flex')
    })

    test('toggleAdvancedSearch() saves "open" to sessionStorage', () => {
        const ctrl = makeSearchController()
        ctrl.toggleAdvancedSearch()
        expect(sessionStorageMock.setItem).toHaveBeenCalledWith('ppa-adv-search', 'open')
    })

    test('_advancedSearchOff() hides .advanced elements', () => {
        const ctrl = makeSearchController()
        ctrl._advancedSearchOn()
        ctrl._advancedSearchOff()
        const segments = document.querySelectorAll('.advanced.segment')
        expect(segments[0].style.display).toBe('none')
    })

    test('_advancedSearchOff() saves "closed" to sessionStorage', () => {
        const ctrl = makeSearchController()
        ctrl._advancedSearchOn()
        ctrl._advancedSearchOff()
        expect(sessionStorageMock.setItem).toHaveBeenLastCalledWith('ppa-adv-search', 'closed')
    })

    test('_setupAdvancedSearch() restores open state from sessionStorage', () => {
        sessionStorageMock.getItem.mockImplementation(key =>
            key === 'ppa-adv-search' ? 'open' : null
        )
        makeSearchController()
        const segments = document.querySelectorAll('.advanced.segment')
        expect(segments[0].style.display).toBe('flex')
    })
})

// -------------------------------------------------------------------------
// Collection inputs (regression for the checkbox active-state bug)
// -------------------------------------------------------------------------
describe('SearchController — collection inputs', () => {
    beforeEach(() => {
        buildDOM()
        sessionStorageMock.clear()
        jest.clearAllMocks()
    })

    afterEach(() => {
        document.body.innerHTML = ''
    })

    test('collections start with active class matching pre-checked state', () => {
        makeSearchController()
        const checked = document.querySelector('#collections input[value="col1"]')
        const uncheckedLabel = document.querySelector('#collections input[value="col3"]').parentElement
        expect(checked.parentElement.classList.contains('active')).toBe(true)
        expect(uncheckedLabel.classList.contains('active')).toBe(false)
    })

    test('unchecking a pre-checked checkbox removes "active" from its parent label', () => {
        makeSearchController()
        const checkbox = document.querySelector('#collections input[value="col1"]')
        const label = checkbox.parentElement
        // starts checked/active — simulate user unchecking
        checkbox.checked = false
        checkbox.dispatchEvent(new Event('change', { bubbles: true }))
        expect(label.classList.contains('active')).toBe(false)
    })

    test('re-checking a checkbox adds "active" back to its parent label', () => {
        makeSearchController()
        const checkbox = document.querySelector('#collections input[value="col1"]')
        const label = checkbox.parentElement
        // uncheck
        checkbox.checked = false
        checkbox.dispatchEvent(new Event('change', { bubbles: true }))
        expect(label.classList.contains('active')).toBe(false)
        // re-check
        checkbox.checked = true
        checkbox.dispatchEvent(new Event('change', { bubbles: true }))
        expect(label.classList.contains('active')).toBe(true)
    })

    test('disabled checkboxes get "disabled" class on parent label on connect', () => {
        makeSearchController()
        const disabledCheckbox = document.querySelector('#collections input[disabled]')
        expect(disabledCheckbox.parentElement.classList.contains('disabled')).toBe(true)
    })

    test('Enter keydown on a checkbox calls click() to toggle it', () => {
        makeSearchController()
        const checkbox = document.querySelector('#collections input[value="col1"]')
        const label = checkbox.parentElement
        // spy on checkbox.click
        let clicked = false
        checkbox.addEventListener('click', () => { clicked = true })
        checkbox.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
        expect(clicked).toBe(true)
    })
})

// -------------------------------------------------------------------------
// Text input / sort state
// -------------------------------------------------------------------------
describe('SearchController — text input and sort', () => {
    beforeEach(() => {
        buildDOM()
        sessionStorageMock.clear()
        jest.clearAllMocks()
    })

    afterEach(() => {
        document.body.innerHTML = ''
    })

    test('onTextInputChange() removes "disabled" from relevanceOptionTargets when text present', () => {
        const relevanceOption = document.createElement('option')
        relevanceOption.classList.add('disabled')
        // sortDropdownTarget must exist — onTextInputChange calls _setDropdownValue on it
        const sortDropdown = document.createElement('div')
        const ctrl = makeSearchController({
            relevanceOptionTargets: [relevanceOption],
            sortDropdownTarget: sortDropdown,
            hasSortDropdownTarget: true,
        })
        const textInput = document.querySelector('[data-search-target="textInput"]')
        textInput.value = 'some query'
        ctrl.onTextInputChange()
        expect(relevanceOption.classList.contains('disabled')).toBe(false)
    })

    test('onTextInputChange() adds "disabled" to relevanceOptionTargets when text is cleared', () => {
        const relevanceOption = document.createElement('option')
        const ctrl = makeSearchController({
            relevanceOptionTargets: [relevanceOption],
        })
        const textInput = document.querySelector('[data-search-target="textInput"]')
        textInput.value = ''
        ctrl.onTextInputChange()
        expect(relevanceOption.classList.contains('disabled')).toBe(true)
    })

    test('preventEnterSubmit() calls preventDefault for Enter key', () => {
        const ctrl = makeSearchController()
        const event = new KeyboardEvent('keydown', { key: 'Enter' })
        event.preventDefault = jest.fn()
        ctrl.preventEnterSubmit(event)
        expect(event.preventDefault).toHaveBeenCalled()
    })

    test('preventEnterSubmit() does not call preventDefault for other keys', () => {
        const ctrl = makeSearchController()
        const event = new KeyboardEvent('keydown', { key: 'a' })
        event.preventDefault = jest.fn()
        ctrl.preventEnterSubmit(event)
        expect(event.preventDefault).not.toHaveBeenCalled()
    })
})
