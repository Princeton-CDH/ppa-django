import PitBar from './pitbar'

$(function(){

    /* dom */
    const $mainNav = $('#main-nav')
    const $mobileNav = $('#mobile-nav')
    const $menuButton = $('.toc.item')
    const $footer = $('footer')
    const $main = $('main')

    /* functions */
    function pushMain($footer, $main) {
        // push main up by footer amount
        $main.css('margin-bottom', `+=${$footer.outerHeight()}`)
    }

    /* bindings */
    new PitBar($mainNav, $mobileNav)
    window.onresize = pushMain($footer, $main)
    $mobileNav
        .sidebar('attach events', $menuButton)
        .sidebar('setting', {
            onChange: () => {
                // swap the hamburger icon for a close icon
                $('.times.icon').toggle()
                $('.sidebar.icon').toggle()
            }
        })
})

