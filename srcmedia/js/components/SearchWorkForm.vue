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
import KeywordSearch from './KeywordSearch'
import { ajax } from '../modules/Utilities'
import debounce from 'lodash/debounce'

export default {
    components: {
        KeywordSearch,
    },
    props: {
        fields: Object, // serialized representation of form
        target: String, // URL to use for requesting results
    },
    methods: {
        /** 
         * Converts the form's data into an object suitable for serializing as
         * the querystring of a URL.
         */
        serialize() {
            let data = new FormData(this.$el)
            let params = new URLSearchParams(data) // not a true Object
            let output = {}
            for(let k of params) {
                output[k[0]] = k[1]
            }
            return output
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
            this.$router.replace({ query: this.serialize() })
            console.log('sending request to', this.target)
        }, 300),
    }
}
</script>
