$(function(){

    /* dom */
    const $mainNav = $('#main-nav')
    const $mobileNav = $('#mobile-nav')
    const $menuButton = $('.toc.item')
    const $footer = $('footer')
    const $main = $('main')

    /* functions */
    $.fn.pitbar = function() {
        let $pitbar = $(this)
        function checkScroll() {
            let scroll = checkScroll.scroll || 0
            let scrolled = $(document).scrollTop()
            if (scrolled - scroll > 25 && scrolled > scroll && scrolled > 90) {
                if (!$pitbar.hasClass('hidden') && !$mobileNav.sidebar('is visible')) {
                    $pitbar.addClass('hidden')
                }
            }
            else if (scrolled < scroll && scroll - scrolled > 5) {
                if ($pitbar.hasClass('hidden')) {
                    $pitbar.removeClass('hidden')
                }
            }
            checkScroll.scroll = scrolled // memoize the scroll value
        }
        $(window).scroll(checkScroll)   
    }
    function pushMain($footer, $main) {
        // push main up by footer amount
        $main.css('margin-bottom', `+=${$footer.outerHeight()}`)
    }

    /* bindings */
    $mainNav.pitbar()
    $mobileNav
        .sidebar('attach events', $menuButton)
        .sidebar('setting', {
            onChange: () => {
                // swap the hamburger icon for a close icon
                $('.times.icon').toggle()
                $('.sidebar.icon').toggle()
            }
        })
    window.onresize = pushMain($footer, $main)
})
