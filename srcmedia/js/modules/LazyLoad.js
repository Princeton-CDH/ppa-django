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
    img.onload = () => {
        // remove the data attributes
        img.removeAttribute('data-src')
        img.removeAttribute('data-srcset')

        // If 2x preview image errors due to HathiTrust Image API throttling,
        // it does not trigger image onerror  because it returns a valid
        // image, even though the HTTP status is 503.
        // Detect based on width of "image currently unavailable" image
        // and remove srcset to fallback to lower-res thumbnail image.
        if (img.naturalWidth == 468) {
            img.removeAttribute('srcset')
        }
    }
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

export {
    loadImage,
    ImageLazyLoader
}

export default ImageLazyLoader
