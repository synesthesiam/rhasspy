<template>
    <div class="container">
        <tree-view :data="actorStates"
                   :options='{ rootObjectKey: "states" }'
                   :hidden="!actorStates"></tree-view>

    </div> <!-- container -->
</template>

<script>
 import StateService from '@/services/StateService'

 export default {
     name: 'ActorStates',
     data: function () {
         return {
             actorStates: {}
         }
     },

     methods: {
         refreshStates: function() {
             StateService.getActorStates()
                         .then(request => {
                             this.actorStates = request.data
                         })
                         .catch(err => this.$parent.error(err))
             setTimeout(this.refreshStates, 1000)
         }
     },

     mounted: function() {
         this.refreshStates()
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
