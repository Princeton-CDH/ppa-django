import Vue from 'vue'
import VueRouter from 'vue-router'

Vue.use(VueRouter)

import clearable from './clearable'
import SearchWorkForm from './components/SearchWorkForm'
import SearchWorkResults from './components/SearchWorkResults'
import ImageLazyLoader from './modules/LazyLoad'

let store = {
    results: ''
}

const router = new VueRouter({
    routes: [{ path: '*' }],
    mode: 'history',
})

const formInstance = new Vue({ // create search instance
    router, // for manipulating the querystring
    render: h => h(SearchWorkForm, {
        props: { ...window.formData, sharedState: store }, // load initial state from Django
    })
})

const resultsInstance = new Vue({
    render: h => h(SearchWorkResults, {
        props: { sharedState: store }
    })
})

$(function(){
    formInstance.$mount('#search-within') // mount form
    resultsInstance.$mount('.ajax-container') // mount results

    $('.question-popup').popup()
    $('#id_query').get().map(clearable)

    const $$pagePreviews = $('img[data-src]')

    new ImageLazyLoader($$pagePreviews.get()) // lazy load images
})