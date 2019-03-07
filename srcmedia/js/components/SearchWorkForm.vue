<template>
    <form id="search-within" class="ui form" @input="onInput" @submit.prevent>
        <fieldset class="ui vertical basic grid segment">
            <legend class="sr-only">text search fields</legend>
            <div class="twelve wide column">
                <keyword-search v-bind="fields.query"></keyword-search>
                <span class="question-popup" data-html="foo text" data-position="top center">
                    <i class="ui question circle icon"></i>
                </span>
            </div>
            <input class="sr-only sr-only-focusable" type="submit" aria-label="submit search">
        </fieldset>
    </form>
</template>

<script>
import debounce from 'lodash/debounce'

import KeywordSearch from './KeywordSearch'
import { ajax } from '../modules/Utilities'
import ImageLazyLoader from '../modules/LazyLoad'

export default {
    components: {
        KeywordSearch,
    },
    props: {
        fields: Object, // serialized representation of form
        target: String, // URL to use for requesting results
        sharedState: Object,
    },
    data() {
        return {
            localState: this.sharedState
        }
    },
    created() {
        this.onInput()
    },
    methods: {
        /** 
         * Serializes the form's data as a URL querystring.
         */
        serialize() {
            return new URLSearchParams(this.dataAsObject()).toString()
        },
        /**
         * Converts the form's data into an object for passing to vue-router's
         * replace() function for updating the querystring.
         */
        dataAsObject() {
            let data = new FormData(this.$el)
            return Object.assign(...Array.from(data).map(d => ({[d[0]]: d[1]})))
        },
        /** 
         * Replaces the URL querystring with the current version of the form's
         * state and requests new search results. Called when any <input> that
         * belongs to the form emits an input event.
         * 
         * Debounced to prevent repeated calls within 300ms intervals, e.g. when
         * the user is typing rapidly into a text input.
         */
        onInput: debounce(function() {            
            this.$router.replace({ query: this.dataAsObject() })
            fetch(`${this.target}?${this.serialize()}`, ajax)
                .then(res => res.text())
                .then(html => {
                    this.localState.results = html
                    this.rebindLazyLoad()
                })
        }, 300),
        rebindLazyLoad() {
            console.log('rebinding to:', Array.from(document.querySelectorAll('img[data-src]')))
            new ImageLazyLoader(Array.from(document.querySelectorAll('img[data-src]'))) // lazy load images
        }
    }
}
</script>
