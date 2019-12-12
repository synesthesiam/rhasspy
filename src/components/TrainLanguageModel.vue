<template>
    <div class="container">
        <form class="form" v-on:submit.prevent="saveSentences">
            <div class="form-group">
                <div class="form-row text-muted pl-1">
                    <p>Example sentences, formatted <a href="https://docs.python.org/3/library/configparser.html">ini style</a>, with each section (intent) containing a <a href="https://rhasspy.readthedocs.io/en/latest/training/#sentencesini">simplified JSGF Grammar</a>.</p>
                </div>
                <div class="form-row text-muted pl-1">
                    <p>Sentences shouldn't contain non-words characters like commas and periods. Optional words are <tt>[bracketed]</tt>. Alternatives are <tt>(separated | by | pipes)</tt>. Rules have an <tt>=</tt> after their name, optionally contain <tt>{tags}</tt>, and are referenced <tt>&lt;by_name&gt;</tt>.</p>
                </div>
                <div class="form-group">
                    <div class="form-row">
                        <button type="submit" class="btn btn-primary"
                                v-bind:class="{ 'btn-danger': sentencesDirty }">Save Sentences</button>
                    </div>
                </div>
                <div class="form-row">
                    <input type="text" name="iniPath" list="iniPaths" />
                    <datalist id="iniPaths">
                        <option value="sentences.ini">sentences.ini</option>
                    </datalist>
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
     data: function () {
         return {
             sentences: '',
             sentencesDirty: false
         }
     },

     methods: {
         saveSentences: function() {
             this.$parent.beginAsync()
             LanguageModelService.update_sentences(JSON.stringify({'sentences.ini': this.sentences}))
                 .then(request => this.$parent.alert(request.data, 'success'))
                 .then(() => {
                     this.$parent.endAsync()
                     if (confirm("Sentences saved. Train Rhasspy?")) {
                         this.$parent.train()
                     }
                     this.sentencesDirty = false
                 })
                 .catch(err => this.$parent.error(err))
         },

         getSentences: function() {
             LanguageModelService.getSentences()
                                 .then(request => {
                                     this.sentences = request.data['sentences.ini']
                                 })
                                 .catch(err => this.$parent.error(err))
         }
     },

     mounted: function() {
         this.sentences = this.getSentences()
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
textarea {
    font-family:Consolas,Monaco,Lucida Console,Liberation Mono,DejaVu Sans Mono,Bitstream Vera Sans Mono,Courier New, monospace;
}
</style>
