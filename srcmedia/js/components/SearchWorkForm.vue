<template>
    <form id="search-within" class="ui form" @input="onInput" @submit="onSubmit">
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

export default {
    components: {
        KeywordSearch,
    },
    props: {
        fields: Object,
    },
    methods: {
        onInput(e) {
            this.$router.replace({ query: this.serialize() })
        },
        onSubmit(e) {
            e.preventDefault()
        },
        serialize() {
            let data = new FormData(this.$el)
            let params = new URLSearchParams(data)
            let output = {}
            for(let k of params) {
                output[k[0]] = k[1]
            }
            return output
        }
    }
}
</script>
