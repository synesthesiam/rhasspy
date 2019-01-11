<template>
    <div class="container">
        <div class="text-muted pl-1">
            <p>
                This is where you manage how Rhasspy expects words to be pronounced in your voice commands.
                You can look up a word in the dictionary below, or have the system guess how an unknown word is pronounced.
            </p>
        </div>
        <form class="form" v-on:submit.prevent="lookupWord">

            <div class="form-row form-group">
                <div class="col-xs-auto">
                    <label for="dict-word" class="col-form-label col-sm-1">Word:</label>
                </div>
                <div class="col">
                    <input id="dict-word" class="form-control" type="text" v-model="dictWord">
                </div>
                <div class="col-xs-auto">
                    <button type="submit" class="btn btn-primary form-control"
                            title="Look up or guess the pronunciation of a word">Lookup</button>
                </div>
                <div class="col-xs-auto">
                    <label for="dict-pronunciations" class="col-form-label col-sm-1">Pronunciations:</label>
                </div>
                <div class="col-xs-auto">
                    <select id="dict-pronunciations" class="form-control" v-model="phonemes">
                        <option disabled value="">Select Pronunciation</option>
                        <option v-for="pronunciation in pronunciations" v-bind:key="pronunciation">{{ pronunciation }}</option>
                    </select>
                </div>
            </div>
            <div class="form-row form-group">
                <div class="col-xs-auto">
                    <label for="dict-phonemes" class="col-form-label col-sm-1">Phonemes:</label>
                </div>
                <div class="col">
                    <input id="dict-phonemes" title="Sphinx Phonemes" class="form-control" type="text" v-model="phonemes">
                </div>
                <div class="col-xs-auto">
                    <button type="button" class="btn btn-success" title="Add this pronunciation to your custom words" @click="addToCustomWords">Add</button>
                </div>
                <div class="col-xs-auto">
                    <input id="espeak-phonemes" title="eSpeak Phonemes" class="form-control" type="text" v-model="espeakPhonemes" readonly>
                </div>
                <div class="col-xs-auto">
                    <button type="button" class="btn btn-secondary" @click="pronouncePhonemes"
                            title="Speak the selected pronunciation">Pronounce</button>
                </div>
                <div class="col-xs-auto">
                    <button type="button" class="btn btn-info" @click="downloadPhonemes"
                            title="Download the selected pronunciation as a WAV file">Download</button>
                </div>
                <div class="col-xs-auto">
                    <select class="form-control" v-model="pronounceType">
                        <option value="phonemes">Phonemes</option>
                        <option value="word">Word</option>
                    </select>
                </div>
            </div>
        </form>

        <div class="row mt-5" :hidden="unknownWords.length == 0">
            <div class="col">
                <h3>Unknown Words</h3>
                <div class="text-muted pl-1">
                    <p>Rhasspy isn't sure how you pronounce these words. Click on each word to see guesses above. Add the correct pronunciations to your custom words.</p>
                </div>
                <ul>
                    <li v-for="pair in unknownWords" v-bind:key="pair[0]">
                        <a href="#" @click="showUnknownWord(pair[0], pair[1])">{{ pair[0] }}</a>
                    </li>
                </ul>
            </div>
        </div>

        <form class="form" v-on:submit.prevent="saveCustomWords">
            <div class="form-group">
                <div class="form-row">
                    <label for="custom-words" class="col-form-label col font-weight-bold">Custom Words:</label>
                </div>
                <div class="form-row text-muted pl-1">
                    <p>These are words whose pronunciations you want to customize. Each line contains a word followed by the phonemes, separated by spaces.</p>
                </div>
                <div class="form-group">
                    <div class="form-row">
                        <button type="submit" class="btn btn-primary"
                                v-bind:class="{ 'btn-danger': customWordsDirty }">Save Custom Words</button>
                    </div>
                </div>
                <div class="form-row">
                    <textarea id="custom-words" class="form-control" style="border-width: 3px" type="text" rows="10" v-model="customWords" v-bind:class="{ 'border-danger': customWordsDirty }" @input="customWordsDirty=true"></textarea>
                </div>
            </div>

            <div class="form-group">
                <div class="form-row">
                    <button type="submit" class="btn btn-primary"
                            v-bind:class="{ 'btn-danger': customWordsDirty }">Save Custom Words</button>
                </div>
            </div>
        </form>

        <div class="row mt-4">
            <div class="col">
                <h3>Phonemes</h3>
                <p>
                    Sphinx uses the following <b>phonemes</b> (units of a spoken word) to describe how a
                    word is pronounced:
                </p>
            </div>
        </div>

        <div class="row mt-3">
            <div class="col">
                <table class="table">
                    <thead class="thead-light">
                        <th scope="col">Phoneme</th>
                        <th scope="col">Example</th>
                        <th scope="col">Translation</th>
                    </thead>
                    <tbody>
                        <tr v-for="pair in examples" v-bind:key="pair[0]">
                            <td>{{ pair[0] }}</td>
                            <td>{{ pair[1].word }}</td>
                            <td>{{ pair[1].phonemes }}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>  <!-- phoneme table -->

    </div> <!-- container -->
</template>

<script>
 import PronounceService from '@/services/PronounceService'

 export default {
     name: 'LookupPronounce',
     props: {
         profile : String,
         unknownWords: Array
     },
     data: function () {
         return {
             dictWord: '',
             phonemes: '',
             espeakPhonemes: '',
             pronunciations: [],
             examples: [],
             pronounceType: 'phonemes',

             customWords: '',
             customWordsDirty: false,
         }
     },

     methods: {
         // Look up word in dictionary or guess pronunciation
         lookupWord: function() {
             this.$parent.beginAsync()
             PronounceService.lookupWord(this.profile, this.dictWord)
                 .then(request => {
                     if (!request.data.in_dictionary) {
                         // Warn user that this word is a guess
                         this.$parent.alert('"' + this.dictWord + '" not in dictionary', 'warning')
                     }

                     this.pronunciations = request.data.pronunciations
                     if (this.pronunciations.length > 0) {
                         // Automatically select the first pronunciation
                         this.phonemes = this.pronunciations[0];
                     }

                     this.espeakPhonemes = request.data.espeak_phonemes
                 })
                 .catch(err => this.$parent.alert(err.response.data, 'danger'))
                 .then(() => this.$parent.endAsync())
         },

         showUnknownWord: function(word, phonemes) {
             this.dictWord = word
             this.phonemes = phonemes
             this.lookupWord()
         },

         // Pronounce word using speakers
         pronouncePhonemes: function() {
             this.$parent.beginAsync()
             var pronounceString = (this.pronounceType == 'word')
                                 ? this.dictWord : this.phonemes

             PronounceService.pronounce(this.profile, pronounceString, this.pronounceType)
                 .catch(err => this.$parent.alert(err.response.data, 'danger'))
                 .then(() => this.$parent.endAsync())
         },

         // Generate WAV file with pronuncation
         downloadPhonemes: function() {
             this.$parent.beginAsync()
             var pronounceString = (this.pronounceType == 'word')
                                 ? this.dictWord : this.phonemes

             PronounceService.download(this.profile, pronounceString, this.pronounceType)
                 .then(request => {
                     var byteArray = new Uint8Array(request.data)
                     var link = window.document.createElement('a')
                     link.href = window.URL.createObjectURL(
                         new Blob([byteArray], { type: 'audio/wav' }))

                     link.download = this.dictWord + '.wav'

                     document.body.appendChild(link)
                     link.click()
                     document.body.removeChild(link)
                 })
                 .catch(err => this.$parent.alert(err.response.data, 'danger'))
                 .then(() => this.$parent.endAsync())
         },

         refreshExamples: function() {
             PronounceService.getPhonemeExamples(this.profile)
                             .then(request => {
                                 this.examples = Object.entries(request.data)
                                 this.examples.sort()
                             })
                             .catch(err => this.$parent.alert(err.response.data, 'danger'))
         },

         saveCustomWords: function() {
             this.$parent.beginAsync()
             PronounceService.updateCustomWords(this.profile, this.customWords)
                 .then(request => this.$parent.alert(request.data, 'success'))
                 .catch(err => this.$parent.alert(err.response.data, 'danger'))
                 .then(() => {
                     this.$parent.endAsync()
                     this.customWordsDirty = false
                 })
         },

         getCustomWords: function() {
             PronounceService.getCustomWords(this.profile)
                             .then(request => {
                                 this.customWords = request.data
                             })
                             .catch(err => this.$parent.alert(err.response.data, 'danger'))
         },

         addToCustomWords: function() {
             if (this.dictWord.length > 0) {
                 this.customWords += '\n' + this.dictWord + ' ' + this.phonemes
                 this.customWordsDirty = true
             }
         }
     },

     mounted: function() {
         this.refreshExamples()
         this.customWords = this.getCustomWords()
     },

     watch: {
         profile() {
             this.refreshExamples()
             this.customWords = this.getCustomWords()
         }
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
