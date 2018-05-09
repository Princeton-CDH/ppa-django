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
                if ($pitbar.transition('is visible') && !$pitbar.transition('is animating')) {
                    if (!$mobileNav.sidebar('is visible')) {
                        $pitbar.transition('slide down')
                    }
                }
            }
            else if (scrolled < scroll && scroll - scrolled > 5) {
                if (!$pitbar.transition('is visible') && !$pitbar.transition('is animating')) {
                    $pitbar.transition('slide down')
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


// if ('undefined' !== typeof window.jQuery || 'undefined' !== typeof window.$) {
//   $(function() {
//     // ribbon
//     console.log('init ribbon');
//     var $ribbon = $('.ribbon');
//     if ($ribbon) {
//         var faded = sessionStorage.getItem('fade-test-banner', true);
//         if (! faded) {
//             $('.ribbon-box').removeClass('fade');
//         }
//         $ribbon.on('click',function(){
//             $('.ribbon-box').addClass('fade');
//             sessionStorage.setItem('fade-test-banner', true);
//         });
//     }
