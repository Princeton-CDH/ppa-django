<template>
    <div class="wrapper" v-html="sharedState.results"></div>
</template>

<script>
export default {
    props: {
        sharedState: Object
    },
}
</script>
