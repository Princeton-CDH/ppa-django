export const toArray = value => Array.isArray(value) ? value : value ? [value] : undefined

export const ajax = {
    headers: { // this header is needed to signal an ajax request to Django
        'X-Requested-With': 'XMLHttpRequest',
    }
}
export const parser = new DOMParser()

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