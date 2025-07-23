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
            expect($(':focus').length).toBe(1)
        })

    })

    describe('feedbackHandler()', () => {

        beforeEach(function () {
            loadFixtures('nav-menu.html')
            this.an = new NavMenu('.about', '.about > .text')
        })

        it('moves up and down the menu based on arrow keys', function() {
            const down = 40
            const up = 38
            const e = $.Event('keydown',
                {
                    keyCode: down,
                    // set about as currentTarget and target for initial state
                    currentTarget: document.getElementsByClassName('.about')[0],
                    target: document.getElementsByClassName('.about')[0]
                }
            )
            // start at about and walk down two
            this.an.$textSelector.trigger(e)
            expect($(':focus').attr('href')).toBe('/history/')
            // get current focused DOM node and simulate the keydown correctly
            e.target = $(':focus').get(0)
            this.an.$textSelector.trigger(e)
            expect($(':focus').attr('href')).toBe('/prosody/')
            // now walk back up
            e.keyCode = up
            e.target = $(':focus').get(0)
            $(':focus').trigger(e)
            expect($(':focus').attr('href')).toBe('/history/')
            e.target = $(':focus').get(0)
            this.an.$textSelector.trigger(e)
            // back to text (about)
            expect($(':focus').hasClass('text')).toBeTruthy()


        })
    })

})