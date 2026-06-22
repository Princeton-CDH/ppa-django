import { Controller } from '@hotwired/stimulus'
import { fromEvent, merge } from 'rxjs'
import { map, debounceTime, distinctUntilChanged } from 'rxjs/operators'
import { ajax, parser } from '../modules/Utilities'
import ImageLazyLoader from '../modules/LazyLoad'

/**
 * Search page controller. Replaces search.js + ReactiveForm.js + PitBar.js.
 *
 * Manages:
 *   - Reactive form submission (AJAX, history pushState)
 *   - Date range validation
 *   - Advanced search toggle (with sessionStorage persistence)
 *   - Sort dropdown / relevance option toggling
 *   - Collection button focus/active states
 *   - Histogram updates (delegates to histogram controller)
 *   - Lazy image loading after results update
 *   - Nav hide-on-scroll (pit bar behaviour for .pusher scroller)
 *
 * Expected structure: see search_form.html and base search page template.
 * Key data attributes referenced in templates:
 *
 *   data-controller="search"
 *   data-search-target="results|paginationTop|resultsCount|minDate|maxDate|
 *                        sortDropdown|sortInput|advancedButton|validation|
 *                        advancedSearchIndicator|textInput|
 *                        relevanceOption|workscount"
 */
export default class SearchController extends Controller {
    static targets = [
        'results',
        'paginationTop',
        'resultsCount',
        'sortDropdown',
        'sortInput',
        'advancedButton',
        'validation',
        'advancedSearchIndicator',
        'textInput',
        'relevanceOption',
        'workscount',
        'form',
        'facets',
    ]

    // pub_date is a MultiWidget rendering to #id_pub_date_0 / #id_pub_date_1.
    // We access them via DOM id rather than Stimulus targets so that no
    // data-search-target attributes need to be threaded through render_field.
    get _minDateInput() { return document.getElementById('id_pub_date_0') }
    get _maxDateInput() { return document.getElementById('id_pub_date_1') }

    connect() {
        this._subscriptions = []
        this._scroll = 0

        this._setupFormReactivity()
        this._setupCollectionInputs()
        this._setupSortDropdown()
        this._setupAdvancedSearch()
        this._onPageLoad()
    }

    disconnect() {
        this._subscriptions.forEach(sub => sub.unsubscribe())
        this._subscriptions = []
    }

    // -------------------------------------------------------------------------
    // Actions (called from data-action attributes in templates)
    // -------------------------------------------------------------------------

    clearDates() {
        const min = this._minDateInput
        const max = this._maxDateInput
        if (min) { min.value = ''; min.dispatchEvent(new Event('input', { bubbles: true })) }
        if (max) { max.value = ''; max.dispatchEvent(new Event('input', { bubbles: true })) }
    }

    toggleAdvancedSearch() {
        const advanced = this.element.querySelectorAll('.advanced')
        const isHidden = advanced[0]?.offsetParent === null ||
            getComputedStyle(advanced[0]).display === 'none'
        isHidden ? this._advancedSearchOn() : this._advancedSearchOff()
    }

    onTextInputChange() {
        const hasText = this.textInputTargets.some(el => el.value.trim() !== '')

        if (hasText) {
            this.relevanceOptionTargets.forEach(el => el.classList.remove('disabled'))
            this._setDropdownValue(this.sortDropdownTarget, 'relevance')
        } else {
            this.relevanceOptionTargets.forEach(el => el.classList.add('disabled'))
            const sortInput = this.hasSortInputTarget ? this.sortInputTarget : null
            if (sortInput) {
                const currentSort = new URLSearchParams(window.location.search).get('sort')
                if (currentSort === 'relevance') {
                    this._setDropdownValue(this.sortDropdownTarget, 'title_asc')
                }
            }
        }
    }

    preventEnterSubmit(event) {
        if (event.key === 'Enter') event.preventDefault()
    }

    // -------------------------------------------------------------------------
    // Private: form reactivity
    // -------------------------------------------------------------------------

    _setupFormReactivity() {
        const form = this.hasFormTarget ? this.formTarget : this.element.querySelector('form')
        if (!form) return

        const inputs = [
            ...form.querySelectorAll('input'),
            ...form.querySelectorAll('select'),
        ]

        const streams = inputs.map(el => this._observeInput(el))
        if (!streams.length) return

        const merged = merge(...streams)
        const sub = merged.pipe(
            map(() => this._serializeForm(form))
        ).subscribe(state => this._submitForm(state))

        this._subscriptions.push(sub)
    }

    _observeInput(element) {
        switch (element.type) {
            case 'checkbox':
            case 'radio':
                return fromEvent(element, 'change').pipe(map(e => e.target.checked))
            case 'select':
                return fromEvent(element, 'input').pipe(map(e => e.target.value))
            case 'text':
            case 'number':
            default:
                return fromEvent(element, 'input').pipe(
                    map(e => e.target.value),
                    debounceTime(750),
                    distinctUntilChanged(),
                )
        }
    }

    _serializeForm(form) {
        return Array.from(new FormData(form)).map(([name, value]) => ({ name, value }))
    }

    _submitForm(state) {
        if (!this._validate()) return

        state = state.filter(field => field.value !== '')

        // If user manually deselected all collections, signal that explicitly
        if (!state.some(field => field.name === 'collections')) {
            state.push({ name: 'collections', value: '' })
        }

        const params = new URLSearchParams(state.map(({ name, value }) => [name, value]))
        const url = `?${params.toString()}`
        window.history.pushState(state, 'PPA Archive Search', url)

        if (this.hasWorkscountTarget) this.workscountTarget.classList.add('loading')

        fetch(`/archive/${url}`, { headers: ajax.headers })
            .then(res => res.text())
            .then(html => this._handleResponse(html))
    }

    _handleResponse(html) {
        const doc = parser.parseFromString(html, 'text/html')

        if (this.hasPaginationTopTarget) {
            const newPagination = doc.querySelector('.page-controls')
            if (newPagination) this.paginationTopTarget.innerHTML = newPagination.innerHTML
        }

        if (this.hasResultsCountTarget) {
            const newCount = doc.querySelector('pre.count')
            if (newCount) this.resultsCountTarget.innerHTML = newCount.innerHTML
        }

        // Update histogram
        const facetScript = doc.querySelector('script#facets')
        if (facetScript) {
            try {
                this._updateHistogram(JSON.parse(facetScript.innerHTML))
            } catch (e) { /* malformed JSON — skip */ }
        }

        if (this.hasResultsTarget) this.resultsTarget.innerHTML = html

        document.dispatchEvent(new Event('ZoteroItemUpdated', { bubbles: true, cancelable: true }))

        if (this.hasWorkscountTarget) this.workscountTarget.classList.remove('loading')

        // Re-initialise lazy loading on new content
        // (tooltips are handled by TooltipController via data-controller attributes)
        new ImageLazyLoader(this.element.querySelectorAll('img[data-src]'))

        this._advancedSearchIndicator()
    }

    // -------------------------------------------------------------------------
    // Private: validation
    // -------------------------------------------------------------------------

    _validate() {
        const min = this._minDateInput
        const max = this._maxDateInput
        const validationEl = this.hasValidationTarget ? this.validationTarget : null

        const show = () => { if (validationEl) validationEl.style.visibility = 'visible' }
        const hide = () => { if (validationEl) validationEl.style.visibility = 'hidden' }

        if (min && !min.checkValidity()) { show(); return false }
        if (max && !max.checkValidity()) { show(); return false }
        if (min && max && min.value && max.value && min.value > max.value) { show(); return false }

        hide()
        return true
    }

    // -------------------------------------------------------------------------
    // Private: histogram
    // -------------------------------------------------------------------------

    _updateHistogram(counts) {
        if (!counts) return
        // Delegate to HistogramController if present on the page
        const histogramEl = this.element.querySelector('[data-controller~="histogram"]')
        if (histogramEl?._stimulusController) {
            histogramEl._stimulusController.update(counts)
        } else if (histogramEl) {
            // Dispatch a custom event that histogram controller can handle
            histogramEl.dispatchEvent(new CustomEvent('search:histogram-update', {
                detail: counts,
                bubbles: false,
            }))
        }
    }

    // -------------------------------------------------------------------------
    // Private: collection inputs
    // -------------------------------------------------------------------------

    _setupCollectionInputs() {
        const fieldset = this.element.querySelector('#collections')
        if (!fieldset) return

        // Delegated listeners — no data-search-target needed on each checkbox
        fieldset.addEventListener('change', e => {
            if (e.target.type === 'checkbox' && e.target.name === 'collections') {
                e.target.parentElement?.classList.toggle('active', e.target.checked)
            }
        })
        fieldset.addEventListener('focus', e => {
            if (e.target.type === 'checkbox') e.target.parentElement?.classList.add('focus')
        }, true)
        fieldset.addEventListener('blur', e => {
            if (e.target.type === 'checkbox') e.target.parentElement?.classList.remove('focus')
        }, true)
        fieldset.addEventListener('keypress', e => {
            if (e.target.type === 'checkbox' && e.key === 'Enter') e.target.click()
        })

        // Disable labels for empty (disabled) checkboxes
        fieldset.querySelectorAll('input[type="checkbox"][disabled]')
            .forEach(el => el.parentElement?.classList.add('disabled'))
    }

    // -------------------------------------------------------------------------
    // Private: sort dropdown
    // -------------------------------------------------------------------------

    _setupSortDropdown() {
        // Sort is now handled by SelectController via data-controller="select".
        // No initialisation needed here; SearchController only needs to be able
        // to read/write the value programmatically via _setDropdownValue().
    }

    _setDropdownValue(el, value) {
        // Delegate to SelectController if present on the element
        const selectEl = el.querySelector('[data-controller~="select"]') || el
        if (selectEl._stimulusController) {
            selectEl._stimulusController.setValue(value)
            return
        }
        // Fallback: set value directly on a native <select>
        const select = el.querySelector('select') || el
        if (select.tagName === 'SELECT' && select.value !== value) {
            select.value = value
            select.dispatchEvent(new Event('input', { bubbles: true }))
        }
    }

    // -------------------------------------------------------------------------
    // Private: advanced search toggle
    // -------------------------------------------------------------------------

    _setupAdvancedSearch() {
        // Restore state from sessionStorage without animating
        if (sessionStorage.getItem('ppa-adv-search') === 'open') {
            this.element.querySelector('.show-advanced')?.classList.add('active')
            this.element.querySelectorAll('.advanced.segment').forEach(el => el.style.display = 'flex')
            this.element.querySelectorAll('.advanced.column').forEach(el => el.style.display = 'inline-block')
        }
    }

    _advancedSearchOn() {
        this.element.querySelector('.show-advanced')?.classList.add('active')
        this.element.querySelectorAll('.advanced.segment').forEach(el => el.style.display = 'flex')
        this.element.querySelectorAll('.advanced.column').forEach(el => el.style.display = 'inline-block')
        this.element.querySelectorAll('.advanced').forEach(el => el.classList.add('is-open'))
        sessionStorage.setItem('ppa-adv-search', 'open')
    }

    _advancedSearchOff() {
        this.element.querySelector('.show-advanced')?.classList.remove('active')
        this.element.querySelectorAll('.advanced').forEach(el => {
            el.classList.remove('is-open')
            el.style.display = 'none'
        })
        sessionStorage.setItem('ppa-adv-search', 'closed')
    }

    _advancedSearchIndicator() {
        const hasAdvancedInput = Array.from(
            this.element.querySelectorAll('.advanced input')
        ).some(el => el.value !== '')

        const indicator = this.hasAdvancedSearchIndicatorTarget
            ? this.advancedSearchIndicatorTarget
            : this.element.querySelector('.show-advanced .search-active')

        if (!indicator) return
        indicator.style.display = hasAdvancedInput ? '' : 'none'
    }

    // -------------------------------------------------------------------------
    // Private: page load initialisation
    // -------------------------------------------------------------------------

    _onPageLoad() {
        // Render histogram from inline facet data
        const facetEl = this.hasFacetsTarget
            ? this.facetsTarget
            : this.element.querySelector('.ajax-container script#facets')
        if (facetEl) {
            try { this._updateHistogram(JSON.parse(facetEl.innerHTML)) } catch (e) { /* skip */ }
        }

        // Tooltips are handled by TooltipController via data-controller="tooltip" attributes.
        // No manual initialisation needed here.

        // Initial validation pass
        this._validate()
        this._advancedSearchIndicator()
    }
}
