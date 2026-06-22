import Parallax from 'parallax-js'

// enable parallax effect on homepage
document.addEventListener('DOMContentLoaded', () => {
    // if user prefers reduced motion, don't enable
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (! mediaQuery.matches) {
        new Parallax(document.getElementById('scene'))
    }
})
