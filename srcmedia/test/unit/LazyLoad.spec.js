import { loadImage, ImageLazyLoader } from '../../js/modules/LazyLoad'

jasmine.getFixtures().fixturesPath = 'base/srcmedia/test/fixtures'

describe('loadImage', () => {

    beforeEach(function() {
        loadFixtures('images.html')
    })

    it('should add a src attribute with the value of the data-src attribute', function() {
        let img = document.querySelector('#one')
        loadImage(img)
        expect(img.src).toEqual(img.getAttribute('data-src'))
    })

    it('should add a srcset attribute with the value of the data-srcset attribute', function() {
        let img = document.querySelector('#one')
        loadImage(img)
        expect(img.srcset).toEqual(img.getAttribute('data-srcset'))
    })

    it('should remove the data-src attribute on load', function() {
        let img = document.querySelector('#one')
        loadImage(img)
        img.onload()
        expect(img.hasAttribute('data-src')).toBe(false)
    })

    it('should remove the data-srcset attribute on load', function() {
        let img = document.querySelector('#one')
        loadImage(img)
        img.onload()
        expect(img.hasAttribute('data-srcset')).toBe(false)
    })

    it('should only copy attributes that exist', function() {
        let img = document.querySelector('#three')
        loadImage(img)
        img.onload()
        expect(img.hasAttribute('srcset')).toBe(false)
    })

    it('should remove the srcset attribute if the image was an error response image', function() {
        let img = document.querySelector('#one')
        loadImage(img)
        spyOnProperty(img, 'naturalWidth', 'get').and.returnValue(468) // error image width
        img.onload()
        expect(img.hasAttribute('srcset')).toBe(false)
    })

})

describe('ImageLazyLoader', () => {

    beforeEach(function() {
        loadFixtures('images.html')
        this.images = Array.from(document.querySelectorAll('img'))
    })

    it('should call loadImage once per image if IntersectionObserver isn\'t available')

    it('should instantiate a single IntersectionObsever when created', function() {
        let mockIOConstructor = jasmine.createSpy().and.callThrough()
        class mockIntersectionObserver {
            constructor() {
                mockIOConstructor()
            }
            observe() {

            }
        }
        window.IntersectionObserver = mockIntersectionObserver
        this.loader = new ImageLazyLoader(this.images)
        expect(mockIOConstructor).toHaveBeenCalledTimes(1)
    })

    it('should call observe() for each image it was passed', function() {
        let mockIOObserve = jasmine.createSpy().and.callThrough()
        class mockIntersectionObserver {
            constructor() {
            }
            observe() {
                mockIOObserve()
            }
        }
        window.IntersectionObserver = mockIntersectionObserver
        this.loader = new ImageLazyLoader(this.images)
        expect(mockIOObserve).toHaveBeenCalledTimes(3)
    })

    it('should call unobserver() when each image is intersecting the viewport', function() {
        let mockIOUnobserve = jasmine.createSpy().and.callThrough()
        let observerCallback
        class mockIntersectionObserver {
            constructor(callback) {
                observerCallback = callback
            }
            observe() {}
            unobserve() { mockIOUnobserve() }
        }
        window.IntersectionObserver = mockIntersectionObserver
        this.loader = new ImageLazyLoader(this.images)
        let mockEntry = { isIntersecting: true, target: this.images[0] }
        // mock image entering the viewport
        observerCallback([mockEntry], {
            unobserve: mockIOUnobserve
        })
        expect(mockIOUnobserve).toHaveBeenCalledWith(this.images[0])
    })


})
