import AboutNavController from './about_nav_controller'
import { makeController } from './__test_utils__'

describe('AboutNavController', () => {
    let element, textTarget, link1, link2, link3

    beforeEach(() => {
        document.body.innerHTML = `
            <div data-controller="about-nav">
                <div data-about-nav-target="text" tabindex="0">About</div>
                <div class="menu">
                    <div class="item"><a href="/page1/">Page 1</a></div>
                    <div class="item"><a href="/page2/">Page 2</a></div>
                    <div class="item"><a href="/page3/">Page 3</a></div>
                </div>
            </div>`
        element = document.querySelector('[data-controller="about-nav"]')
        textTarget = document.querySelector('[data-about-nav-target="text"]')
        link1 = document.querySelector('.item:nth-child(1) a')
        link2 = document.querySelector('.item:nth-child(2) a')
        link3 = document.querySelector('.item:nth-child(3) a')
    })

    test('focusin on element adds "hovered" class', () => {
        makeController(AboutNavController, element, { text: textTarget })
        element.dispatchEvent(new Event('focusin', { bubbles: true }))
        expect(element.classList.contains('hovered')).toBe(true)
    })

    test('focusout on element removes "hovered" class', () => {
        makeController(AboutNavController, element, { text: textTarget })
        element.dispatchEvent(new Event('focusin', { bubbles: true }))
        element.dispatchEvent(new Event('focusout', { bubbles: true }))
        expect(element.classList.contains('hovered')).toBe(false)
    })

    test('ArrowDown from text target focuses first menu link', () => {
        makeController(AboutNavController, element, { text: textTarget })
        link1.focus = jest.fn()
        // dispatch from textTarget — it bubbles up to the controller listener
        // controller checks ev.target.nodeName: textTarget is DIV, so goes to "first link" branch
        textTarget.dispatchEvent(new KeyboardEvent('keydown', { code: 'ArrowDown', bubbles: true }))
        expect(link1.focus).toHaveBeenCalled()
    })

    test('ArrowDown from a menu link focuses the next link', () => {
        makeController(AboutNavController, element, { text: textTarget })
        link2.focus = jest.fn()
        link1.dispatchEvent(new KeyboardEvent('keydown', { code: 'ArrowDown', bubbles: true }))
        expect(link2.focus).toHaveBeenCalled()
    })

    test('ArrowUp from a menu link focuses the previous link', () => {
        makeController(AboutNavController, element, { text: textTarget })
        link1.focus = jest.fn()
        link2.dispatchEvent(new KeyboardEvent('keydown', { code: 'ArrowUp', bubbles: true }))
        expect(link1.focus).toHaveBeenCalled()
    })

    test('ArrowUp from the first menu link focuses text target', () => {
        makeController(AboutNavController, element, { text: textTarget })
        textTarget.focus = jest.fn()
        link1.dispatchEvent(new KeyboardEvent('keydown', { code: 'ArrowUp', bubbles: true }))
        expect(textTarget.focus).toHaveBeenCalled()
    })

    test('disconnect() removes event listeners', () => {
        const ctrl = makeController(AboutNavController, element, { text: textTarget })
        ctrl.disconnect()
        element.dispatchEvent(new Event('focusin', { bubbles: true }))
        expect(element.classList.contains('hovered')).toBe(false)
    })
})
