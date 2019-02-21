/**
 * Given a single image tag, replace its placeholder content stored in the src
 * attribute with the "real" image stored in its data-src attribute.
 * 
 * This function is designed to defer loading of images until the DOM is
 * finished rendering, so that content doesn't move around while the page loads.
 * 
 * @param {HTMLElement} img 
 */
const loadImage = img => {
    img.setAttribute('src', img.getAttribute('data-src')) // replace with real image
    img.setAttribute('srcset', img.getAttribute('data-srcset'))
    img.onload = () => { // remove the data attributes
        img.removeAttribute('data-src')
        img.removeAttribute('data-srcset')
    }
    // TODO error handling
    // img.onerror = () => 
}

/**
 * Class that creates an instance of an IntersectionObserver that will call
 * `loadImage()` when an image has scrolled into view.
 * 
 * If the API is unavailable, it will instead call loadImage() alone to defer
 * loading until the DOM has rendered.
 */
class ImageLazyLoader {

    /**
     * @param {Array<HTMLElement>} images 
     */
    constructor(images) {
        if ('IntersectionObserver' in window) {
            let observer = new IntersectionObserver((items, observer) => {
                items.forEach(item => {
                    if (item.isIntersecting) {
                        loadImage(item.target)
                        observer.unobserve(item.target)
                    }
                })
            })
            images.forEach(img => observer.observe(img))
        } else {
            images.forEach(img => loadImage(img))
        }
    }
}

export default ImageLazyLoader