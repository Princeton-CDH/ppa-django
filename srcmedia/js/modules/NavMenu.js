export default class AboutNav {
    constructor(selector, textSelector) {

        let self = this
        self.$aboutMenu = $(selector)
        self.$textSelector = $(textSelector)

        // bind a listener for focusinout and file hover for semanticui
        // css so that the menu appears for tab navigation
        self.$aboutMenu.focusin(() => self.$aboutMenu.addClass('hovered'))
        self.$aboutMenu.focusout(() => self.$aboutMenu.removeClass('hovered'))

        // also enable for keypresses on up and down to move up and down the
        // menu
        self.$aboutMenu.keydown(self.keydownHandler.bind(self))

    }

    keydownHandler(ev) {
        // if down arrow, target the next link element
        if (ev.keyCode === 40) {
            // using raw JS to determine we're on a link element
            if (ev.target.nodeName === 'A') {
                // if on a link, get its parent, next sibling, and child a element
                // and focus
                $(ev.target).parent().next().children('a').focus()
            } else {
                // if on the 'about' text itself, get its sibling div .menu
                // child divs, first, and then focus on its a element
                $(ev.target)
                    .siblings('.menu')
                    .children('div')
                    .first()
                    .children('a')
                    .focus()
            }
        }
        // if up arrow, target the previous link element or about menu text
        if (ev.keyCode === 38) {
            // check if there's a previous link
            const $nextLink = $(ev.target).parent().prev().children('a')
            // if there isn't, target the about text that has tabindex for
            // menu
            if ($nextLink.length === 0) {
                this.$textSelector.focus()
            } else {
                // otherwise target the previous link
                $nextLink.focus()
            }
        }
    }

}