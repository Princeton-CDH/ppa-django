import PitBar from './pitbar'

$(function(){

    /* dom */
    const $mainNav = $('#main-nav')
    const $mobileNav = $('#mobile-nav')
    const $menuButton = $('.toc.item')
    const $mobileDropdown = $('#mobile-nav .dropdown.item')

    /* bindings */
    let pb = new PitBar($mainNav, $mobileNav)

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

    $mobileDropdown.click(() => $mobileDropdown.toggleClass('active'))
})
