import { Component } from './common'

describe('Component', () => {

    test('keeps a reference to its element', () => {
        document.body.innerHTML = `<div></div>`
        const element = document.querySelector('div') as HTMLDivElement
        const c = new Component(element)
        expect(c.element).toBe(element)
    })

})