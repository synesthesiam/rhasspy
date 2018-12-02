<template>
    <div class="container">
        <form class="form" v-on:submit.prevent="saveSentences">
            <div class="form-group">
                <div class="form-row">
                    <label for="sentences" class="col-form-label col font-weight-bold">Intent Examples:</label>
                </div>
                <div class="form-row text-muted pl-1">
                    <p>Example sentences, formatted <a href="https://docs.python.org/3/library/configparser.html">ini style</a>, with each section (intent) containing a simplified <a href="https://www.w3.org/TR/jsgf/">JSGF Grammar</a>.</p>
                </div>
                <div class="form-row text-muted pl-1">
                    <p>Sentences shouldn't contain non-words characters like commas and periods. Rules have an <tt>=</tt> and optionally a <tt>{tag}</tt>.</p>
                </div>
                <div class="form-group">
                    <div class="form-row">
                        <button type="submit" class="btn btn-primary"
                                v-bind:class="{ 'btn-danger': sentencesDirty }">Save Sentences</button>
                    </div>
                </div>
                <div class="form-row">
                    <textarea id="sentences" class="form-control" style="border-width: 3px" type="text" rows="25"
                              v-model="sentences" v-bind:class="{ 'border-danger': sentencesDirty }"
                              @input="sentencesDirty=true"></textarea>
                </div>
            </div>

            <div class="form-group">
                <div class="form-row">
                    <button type="submit" class="btn btn-primary"
                            v-bind:class="{ 'btn-danger': sentencesDirty }">Save Sentences</button>
                </div>
            </div>
        </form>

    </div> <!-- container -->
</template>

<script>
 import LanguageModelService from '@/services/LanguageModelService'

 export default {
     name: 'TrainLangaugeModel',
     props: { profile : String },
     data: function () {
         return {
             sentences: '',
             sentencesDirty: false
         }
     },

     methods: {
         saveSentences: function() {
             this.$parent.beginAsync()
             LanguageModelService.update_sentences(this.profile, this.sentences)
                 .then(request => this.$parent.alert(request.data, 'success'))
                 .catch(err => this.$parent.alert(err.response.data, 'danger'))
                 .then(() => {
                     this.$parent.endAsync()
                     this.sentencesDirty = false
                 })
         },

         getSentences: function() {
             LanguageModelService.getSentences(this.profile)
                                 .then(request => {
                                     this.sentences = request.data
                                 })
                                 .catch(err => this.$parent.alert(err.response.data, 'danger'))
         }
     },

     mounted: function() {
         this.sentences = this.getSentences()
     },

     watch: {
         profile() {
             this.sentences = this.getSentences()
         }
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
textarea {
    font-family:Consolas,Monaco,Lucida Console,Liberation Mono,DejaVu Sans Mono,Bitstream Vera Sans Mono,Courier New, monospace;
}
</style>
