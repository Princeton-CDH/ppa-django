export default class AboutNav {
    /**
     * Binds a keyboard navigation events using tab and
     * up/down arrow keys to a CSS element structured as a
     * semantic ui menu.
     *
     * @param {any} selector - JQuery or CSS selector for menu div
     * @param {any} textSelector - JQuery or CSS selector for menu text div (i.e. name of menu)
    */
    constructor(selector, textSelector) {

        let self = this
        self.$aboutMenu = $(selector)
        self.$textSelector = $(textSelector)

        // bind a listener for focusinout and file hover for semanticui
        // css so that the menu appears for tab navigation
        self.$aboutMenu.on('focusin', () => self.$aboutMenu.addClass('hovered'))
        self.$aboutMenu.on('focusout', () => self.$aboutMenu.removeClass('hovered'))

        // also enable for keypresses on up and down to move up and down the
        // menu
        self.$aboutMenu.on('keydown', self.keydownHandler.bind(self))

    }
    /**
     * Handler for keydown events on menu items.
     *
     * @param {JQuery.KeyDownEvent} ev - a jQuery keydown event
    */
    keydownHandler(ev) {
        // if down arrow, target the next link element
        if (ev.originalEvent.code === 'ArrowDown') {
            // using raw JS to determine we're on a link element
            if (ev.target.nodeName === 'A') {
                // if on a link, get its parent, next sibling, and child a element
                // and focus
                $(ev.target).parent().next().children('a').trigger('focus')
            } else {
                // if on the 'about' text itself, get its sibling div .menu
                // child divs, first, and then focus on its a element
                $(ev.target)
                    .siblings('.menu')
                    .children('div')
                    .first()
                    .children('a')
                    .trigger('focus')
            }
        }
        // if up arrow, target the previous link element or about menu text
        if (ev.originalEvent.code === 'ArrowUp') {
            // check if there's a previous link
            const $nextLink = $(ev.target).parent().prev().children('a')
            // if there isn't, target the about text that has tabindex for
            // menu
            if ($nextLink.length === 0) {
                this.$textSelector.trigger('focus')
            } else {
                // otherwise target the previous link
                $nextLink.trigger('focus')
            }
        }
    }

}