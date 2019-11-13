<template>
    <div class="container">
        <form class="form" v-on:submit.prevent="saveSlots">
            <div class="form-group">
                <div class="form-row text-muted pl-1">
                    <p>
                        Slots are named sets of values, referenced by <tt>$slotName</tt> in your sentences.
                        <br>
                        The JSON object below should contain slot name keys and lists of values. For example:
                    </p>
                    <pre><code>{ "color": ["red", "green", "blue"], "direction": ["left", "right"] }</code></pre>
                </div>
                <div class="form-group">
                    <div class="form-row">
                        <button type="submit" class="btn btn-primary"
                                v-bind:class="{ 'btn-danger': slotsDirty }">Save Slots</button>
                    </div>
                </div>
                <div class="form-row">
                    <textarea id="slots" class="form-control" style="border-width: 3px" type="text" rows="25"
                              v-model="slots" v-bind:class="{ 'border-danger': slotsDirty }"
                              @input="slotsDirty=true"></textarea>
                </div>
            </div>

            <div class="form-group">
                <div class="form-row">
                    <button type="submit" class="btn btn-primary"
                            v-bind:class="{ 'btn-danger': slotsDirty }">Save Slots</button>
                </div>
            </div>
        </form>

    </div> <!-- container -->
</template>

<script>
 import LanguageModelService from '@/services/LanguageModelService'

 export default {
     name: 'Slots',
     data: function () {
         return {
             slots: '',
             slotsDirty: false
         }
     },

     methods: {
         saveSlots: function() {
             this.$parent.beginAsync()
             LanguageModelService.update_slots(this.slots)
                 .then(request => this.$parent.alert(request.data, 'success'))
                 .then(() => {
                     this.$parent.endAsync()
                     if (confirm("Slots saved. Train Rhasspy?")) {
                         this.$parent.train()
                     }
                     this.slotsDirty = false
                 })
                 .catch(err => this.$parent.error(err))
         },

         getSlots: function() {
             LanguageModelService.getSlots()
                                 .then(request => {
                                     this.slots = JSON.stringify(request.data, null, 4)
                                 })
                                 .catch(err => this.$parent.error(err))
         }
     },

     mounted: function() {
         this.slots = this.getSlots()
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
textarea {
    font-family:Consolas,Monaco,Lucida Console,Liberation Mono,DejaVu Sans Mono,Bitstream Vera Sans Mono,Courier New, monospace;
}
</style>
