<template>
    <div class="container">
        <div class="text-muted pl-1">
            <p>
                This log is streamed live from your Rhasspy server at <tt>ws://{{ host() }}/api/events/log</tt>
            </p>
        </div>
        <form class="form">
            <div class="form-group">
                <div class="form-row">
                    <button type="button" class="btn btn-primary" @click="clearLog()">Clear Log</button>
                </div>
            </div>
        </form>
        <textarea id="rhasspy-log" class="form-control" type="text" rows="25" v-model="rhasspyLog"></textarea>
    </div> <!-- container -->
</template>

<script>
 export default {
     name: 'RhasspyLog',
     props: {
         rhasspyLog : String
     },

     methods: {
         host: function() {
             return window.location.host
         },

         clearLog: function() {
             this.$parent.rhasspyLog = ''
         }
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
