/**
 * Miscellaneous utility functions taken from Winthrop - note some of these
 * may not currently be in use.
 */

export const toArray = value => Array.isArray(value) ? value : value ? [value] : undefined

export const ajax = {
    headers: { // this header is needed to signal an ajax request to Django
        'X-Requested-With': 'XMLHttpRequest',
    }
}
export const parser = new DOMParser()

/**
 * Reducer that converts a JSON response containing facet data into an object
 * with a map-like structure (key-value).
 */
export const reduceFacets = (acc, cur) => {
    if (acc[cur.facet]) {
        if (!Array.isArray(acc[cur.facet])) {
            acc[cur.facet] = toArray(acc[cur.facet])
        }
        acc[cur.facet].push(cur.value)
    }
    else acc[cur.facet] = cur.value
    return acc
}