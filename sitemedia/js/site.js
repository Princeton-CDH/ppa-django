$(function(){

    /* dom */
    const $mainNav = $('#main-nav')
    const $mobileNav = $('#mobile-nav')
    const $menuButton = $('.toc.item')

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
})
