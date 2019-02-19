<template>
    <div class="field">
        <label :for="id">{{ label }}</label>
        <div class="ui left icon input">
            <i class="search icon"></i>
            <input type="search" :id="id" :name="name" :placeholder="placeholder" v-model="query">
        </div>
    </div>
</template>

<script>
export default {
    props: {
        id: String,
        name: String,
        label: String,
        placeholder: String,
        value: String,
        disabled: Boolean,
        required: Boolean,
    },
    data() {
        return {
            query: this.value
        }
    }
}
</script>
