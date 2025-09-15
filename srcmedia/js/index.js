import PitBar from './pitbar'
import NavMenu from './modules/NavMenu'
import 'fomantic-ui-less/semantic.less'
import 'fomantic-ui/dist/semantic.min.js'

document.firstElementChild.classList.remove('no-js') // remove the no-js class

$(function(){

    /* dom */
    const $mainNav = $('#main-nav')
    const $mobileNav = $('#mobile-nav')
    const $menuButton = $('.toc.item')
    const $mobileDropdown = $('#mobile-nav .dropdown.item')
    const $aboutMenu = $('.about')
    const $aboutMenuText = $('.about > .text')

    /* bindings */
    let pb = new PitBar($mainNav, $mobileNav)
    let an = new NavMenu($aboutMenu, $aboutMenuText)

    $mobileNav
        .sidebar('attach events', $menuButton)
        .sidebar('setting', {
            onChange: () => {
                // swap the hamburger icon for a close icon
                $('.close.icon').toggle()
                $('.menu.icon').toggle()
            },
            onVisible: () => $('.header.brand .item').addClass('hidden'),
            onHidden: () => $('.header.brand .item').removeClass('hidden'),
        })

    $mobileDropdown.on("click", () => $mobileDropdown.toggleClass('active'))


})

