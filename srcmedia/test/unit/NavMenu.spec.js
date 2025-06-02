import NavMenu from '../../js/modules/NavMenu.js'

jasmine.getFixtures().fixturesPath = 'base/srcmedia/test/fixtures/'

describe('NavMenu', () => {



    describe('constructor()', () => {

        beforeEach(function () {
            loadFixtures('nav-menu.html')
            this.an = new NavMenu('.about', '.about > .text')
        })

        it('binds selectors to self as jQuery objects', function() {
            expect(this.an.$aboutMenu[0]).toBe($('.about')[0])
            expect(this.an.$textSelector[0]).toBe($('.about > .text')[0])
        })

        it('binds handler for adding/removing hovered class', function() {
            expect(this.an.$aboutMenu.hasClass('hovered')).toBeFalsy()
            this.an.$aboutMenu.focusin()
            expect(this.an.$aboutMenu.hasClass('hovered')).toBeTruthy()
            this.an.$aboutMenu.focusout()
            expect(this.an.$aboutMenu.hasClass('hovered')).toBeFalsy()
        })

        it('binds handler to keypress event for $aboutMenu', function() {
            // minimal test to ensure binding happened
            const e = $.Event('keydown')
            e.keyCode = 40
            this.an.$textSelector.trigger(e)
            expect(document.activeElement.getAttribute('href')).toBe('/history/')
        })

    })

    describe('keydownHandler()', () => {

        beforeEach(function () {
            loadFixtures('nav-menu.html')
            this.an = new NavMenu('.about', '.about > .text')
        })

        it('moves up and down the menu based on arrow keys', function() {
            const down = 40
            const up = 38
            const text = document.querySelector('.about > .text')
            const historyLink = document.querySelector('a[href="/history/"]')
            const prosodyLink = document.querySelector('a[href="/prosody/"]')

            spyOn(historyLink, 'focus').and.callThrough()
            const e1 = $.Event('keydown', { keyCode: down })

            // start at about and walk down two
            $(text).trigger(e1);
            expect(historyLink.focus).toHaveBeenCalled()

            // get current focused DOM node and simulate the keydown correctly
            spyOn(prosodyLink, 'focus').and.callThrough()
            const e2 = $.Event('keydown', { keyCode: down })
            $(historyLink).trigger(e2)
            expect(prosodyLink.focus).toHaveBeenCalled()

            // now walk back up
            const e3 = $.Event('keydown', { keyCode: up })
            $(prosodyLink).trigger(e3)
            expect(document.activeElement.getAttribute('href')).toBe('/history/')

            // back to text (about)
            const e4 = $.Event('keydown', { keyCode: up })
            $(historyLink).trigger(e4)
            expect(document.activeElement.classList.contains('text')).toBe(true)

        })
    })

})