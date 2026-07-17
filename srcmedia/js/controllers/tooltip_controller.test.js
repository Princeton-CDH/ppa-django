import TooltipController from './tooltip_controller'
import { makeController } from './__test_utils__'

describe('TooltipController', () => {
    let element

    beforeEach(() => {
        document.body.innerHTML = `
            <span data-controller="tooltip">
                <i class="ui question circle icon"></i>
            </span>`
        element = document.querySelector('[data-controller="tooltip"]')

        // jsdom returns all zeros for getBoundingClientRect — provide a real-ish rect
        element.getBoundingClientRect = jest.fn().mockReturnValue({
            top: 100, bottom: 120, left: 200, right: 250, width: 50, height: 20,
        })
    })

    afterEach(() => {
        document.querySelectorAll('.ppa-tooltip').forEach(el => el.remove())
    })

    function make(content = 'Help text', position = 'top') {
        return makeController(TooltipController, element, {}, { content, position })
    }

    test('connect() sets aria-describedby on element', () => {
        make()
        expect(element.getAttribute('aria-describedby')).toMatch(/^tooltip-/)
    })

    test('connect() adds tabindex="0" if element is not focusable', () => {
        make()
        expect(element.getAttribute('tabindex')).toBe('0')
    })

    test('connect() does not overwrite an existing tabindex', () => {
        element.setAttribute('tabindex', '2')
        make()
        expect(element.getAttribute('tabindex')).toBe('2')
    })

    test('mouseenter creates .ppa-tooltip in document.body', () => {
        make()
        element.dispatchEvent(new MouseEvent('mouseenter'))
        const tooltip = document.querySelector('.ppa-tooltip')
        expect(tooltip).not.toBeNull()
        expect(tooltip.textContent).toBe('Help text')
    })

    test('tooltip element has role="tooltip"', () => {
        make()
        element.dispatchEvent(new MouseEvent('mouseenter'))
        const tooltip = document.querySelector('.ppa-tooltip')
        // el.role (IDL attribute) and el.getAttribute('role') are equivalent in real browsers;
        // jsdom sets the property but getAttribute returns null, so check the property directly.
        expect(tooltip.role).toBe('tooltip')
    })

    test('tooltip id matches aria-describedby', () => {
        make()
        element.dispatchEvent(new MouseEvent('mouseenter'))
        const describedBy = element.getAttribute('aria-describedby')
        expect(document.getElementById(describedBy)).not.toBeNull()
    })

    test('mouseleave removes the tooltip', () => {
        make()
        element.dispatchEvent(new MouseEvent('mouseenter'))
        element.dispatchEvent(new MouseEvent('mouseleave'))
        expect(document.querySelector('.ppa-tooltip')).toBeNull()
    })

    test('second mouseenter does not create a duplicate tooltip', () => {
        make()
        element.dispatchEvent(new MouseEvent('mouseenter'))
        element.dispatchEvent(new MouseEvent('mouseenter'))
        expect(document.querySelectorAll('.ppa-tooltip').length).toBe(1)
    })

    test('tooltip class includes the position modifier', () => {
        make('Help text', 'bottom')
        element.dispatchEvent(new MouseEvent('mouseenter'))
        expect(document.querySelector('.ppa-tooltip').classList.contains('ppa-tooltip--bottom')).toBe(true)
    })

    test('focusin shows tooltip, focusout hides it', () => {
        make()
        element.dispatchEvent(new Event('focusin'))
        expect(document.querySelector('.ppa-tooltip')).not.toBeNull()
        element.dispatchEvent(new Event('focusout'))
        expect(document.querySelector('.ppa-tooltip')).toBeNull()
    })

    test('disconnect() hides tooltip and removes listeners', () => {
        const ctrl = make()
        element.dispatchEvent(new MouseEvent('mouseenter'))
        ctrl.disconnect()
        expect(document.querySelector('.ppa-tooltip')).toBeNull()
        // listeners removed — mouseenter no longer shows tooltip
        element.dispatchEvent(new MouseEvent('mouseenter'))
        expect(document.querySelector('.ppa-tooltip')).toBeNull()
    })
})
