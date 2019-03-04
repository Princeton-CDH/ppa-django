export default class PitBar {
    /**
     * A basic "pit bar" behavior: hide the element when the user scrolls down
     * quickly and bring it back when the user scrolls up quickly.
     * 
     * Optional second param is for another menu, e.g. for mobile, that when
     * visible should disable the "pit bar" behavior.
     * 
     * @param {jQuery} pitbar jQuery element to use as pitbar
     * @param {jQuery} mobileNav jQuery element that freezes pitbar when visible
     */

    constructor(pitbar, mobileNav) {
        this.pitbar = pitbar
        this.mobileNav = mobileNav || false
        this.scroll = 0
        $('.pusher').scroll(this.checkScroll.bind(this)) // prevents using scroll event as context
    }

    checkScroll() {
        let scrolled = $('.pusher').scrollTop()
        if (scrolled - this.scroll > 25 && scrolled > this.scroll && scrolled > 90) { // scroll down
            if (!this.pitbar.hasClass('hidden')) {
                if (this.mobileNav && !this.mobileNav.hasClass('visible')) {
                    this.pitbar.addClass('hidden')
                }
            }
        }
        else if (scrolled < this.scroll && this.scroll - scrolled > 5) { // scroll up
            if (this.pitbar.hasClass('hidden')) {
                this.pitbar.removeClass('hidden')
            }
        }
        this.scroll = scrolled
    }
}