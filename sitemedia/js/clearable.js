const button = () => $('<i/>', { class: 'clear times icon' })

const clearable = element => {
    let c = clear(element)
    let b = button().click(c)
    $(element).val() == '' ? b.hide() : b.show()
    b.insertAfter(element)
    $(element).on('input', onInput)
}

const clear = element => () => {
    $(element).val('')
    element.dispatchEvent(new Event('input'))
}

const onInput = event => {
    let b = $(event.target).parent().find('.clear.times.icon')
    $(event.target).val() == '' ? b.hide() : b.show()
}

export default clearable