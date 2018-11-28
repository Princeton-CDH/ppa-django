/**
 * Generates a new DOM element for the button that will clear a field.
 * 
 * @returns {jQuery}
 */
const button = () => $('<i/>', { class: 'clear times icon' })

/**
 * Given an input element, adds a button immediately after the element in
 * the DOM that has a bound click handler to clear the field.
 * 
 * @param {HTMLElement} element
 */
const clearable = element => {
    let c = clear(element)
    let b = button().click(c)
    $(element).val() == '' ? b.hide() : b.show()
    b.insertAfter(element)
    $(element).on('input', onInput)
}

/**
 * Returns a function that will clear a provided element and dispatch an input
 * event to inform other handlers.
 * 
 * @param {HTMLElement} element 
 * @returns {function}
 */
const clear = element => () => {
    $(element).val('')
    element.dispatchEvent(new Event('input'))
}

/**
 * Checks if the field is empty and hides/shows the clear button appropriately.
 * Should be bound to the 'input' event with .on('input').
 * 
 * @param {Event} event 
 */
const onInput = event => {
    let b = $(event.target).parent().find('.clear.times.icon')
    $(event.target).val() == '' ? b.hide() : b.show()
}

export default clearable