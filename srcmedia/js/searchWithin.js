import Vue from 'vue'
import VueRouter from 'vue-router'

Vue.use(VueRouter)

import clearable from './clearable'
import SearchWorkForm from './components/SearchWorkForm'
import ImageLazyLoader from './modules/LazyLoad'

const router = new VueRouter({
    routes: [{ path: '*' }],
    mode: 'history',
})

const vm = new Vue({ // create search instance
    router, // for manipulating the querystring
    render: h => h(SearchWorkForm, {
        props: { ...window.formData }, // load initial state from Django
    })
})

$(function(){
    vm.$mount('#search-within') // mount vue
    $('.question-popup').popup()
    $('#id_query').get().map(clearable)

    const $$pagePreviews = $('img[data-src]')

    new ImageLazyLoader($$pagePreviews.get()) // lazy load images
})