/**
 * Test helper for Stimulus controllers.
 *
 * Stimulus's Controller constructor takes a Context object and defines
 * `element` / `identifier` as getters backed by `this.context.scope`.
 * Class-field arrow functions (_show = () => {}) are only bound during
 * `new`, so Object.create alone won't work.
 *
 * We pass a minimal mock context to `new` so the constructor runs normally
 * (binding class-field arrow functions), then override the scope getters and
 * wire targets/values manually before calling connect().
 *
 * Usage:
 *   const ctrl = makeController(MyController, element, { input, button }, { color: 'red' })
 *
 * @param {typeof import('@hotwired/stimulus').Controller} ControllerClass
 * @param {HTMLElement} element  - the controller root element
 * @param {Record<string, HTMLElement|null>} targets  - map of target name → element
 * @param {Record<string, any>} values  - map of value name → value
 * @returns connected controller instance
 */
export function makeController(ControllerClass, element, targets = {}, values = {}) {
    // Minimal mock context — just enough for the constructor to not throw.
    // `scope` is what the base class reads for element/identifier getters.
    const mockScope = { element, identifier: 'test', schema: {} }
    const mockContext = {
        application: { logFormattedMessage: () => {} },
        scope: mockScope,
    }

    const ctrl = new ControllerClass(mockContext)

    // Wire targets: fooTarget, hasFooTarget, fooTargets
    for (const [name, el] of Object.entries(targets)) {
        const cap = name[0].toUpperCase() + name.slice(1)
        ctrl[`${name}Target`] = el
        ctrl[`has${cap}Target`] = el != null
        ctrl[`${name}Targets`] = el != null ? [el] : []
    }

    // Wire values: fooValue
    for (const [name, val] of Object.entries(values)) {
        ctrl[`${name}Value`] = val
    }

    ctrl.connect()
    return ctrl
}
