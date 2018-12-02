<template>
    <div id="app">
        <!-- Top Bar -->
        <nav class="navbar navbar-expand-md navbar-dark bg-dark fixed-top">
            <div class="navbar-container">
                <img class="navbar-brand" v-bind:class="spinnerClass" src="/img/microphone.png">
                <a href="/" class="text-white font-weight-bold">Rhasspy Voice Assistant</a>
                <a href="/api/" class="badge badge-info ml-2">API</a>
            </div>

            <div class="navbar-container ml-auto">
                <label for="profiles" class="text-white">Profile:</label>
                <select id="profiles" class="ml-2" v-model="profile">
                    <option disabled value="">Select Profile</option>
                    <option v-for="profile in profiles" v-bind:key="profile">{{ profile }}</option>
                </select>
                <button class="btn btn-success ml-3" @click="train" :disabled="this.training">Re-Train</button>
                <button class="btn btn-info ml-3" @click="reload">Reload</button>
            </div>
        </nav>

        <div class="main-container">
            <div class="alert" v-bind:class="alertClass" role="alert" v-if="hasAlert">
                {{ alertText }}
            </div>

            <ul class="nav nav-tabs" id="myTab" role="tablist">
                <li class="nav-item">
                    <a class="nav-link active" id="speech-tab" data-toggle="tab" href="#speech" role="tab" aria-controls="speech" aria-selected="false">Speech</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" id="language-tab" data-toggle="tab" href="#language" role="tab" aria-controls="language" aria-selected="false">Sentences</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" id="pronounce-tab" data-toggle="tab" href="#pronounce" role="tab" aria-controls="pronounce" aria-selected="true">Words</a>
                </li>
            </ul>
            <div class="tab-content" id="myTabContent">
                <div class="tab-pane fade show active" id="speech" role="tabpanel" aria-labelledby="speech-tab">
                    <TranscribeSpeech :profile="profile" />
                </div>
                <div class="tab-pane fade" id="language" role="tabpanel" aria-labelledby="language-tab">
                    <TrainLanguageModel :profile="profile" />
                </div>
                <div class="tab-pane fade" id="pronounce" role="tabpanel" aria-labelledby="pronounce-tab">
                    <LookupPronounce :profile="profile" :unknownWords="unknownWords" />
                </div>
            </div>

        </div> <!-- main container -->
    </div>
</template>

<script>
 import ProfileService from '@/services/ProfileService'
 import LanguageModelService from '@/services/LanguageModelService'
 import PronounceService from '@/services/PronounceService'

 import LookupPronounce from './components/LookupPronounce.vue'
 import TrainLanguageModel from './components/TrainLanguageModel.vue'
 import TranscribeSpeech from './components/TranscribeSpeech.vue'

 export default {
     name: 'app',
     components: {
         LookupPronounce,
         TrainLanguageModel,
         TranscribeSpeech
     },

     data: function() {
         return {
             hasAlert: false,
             alertText: '',
             alertClass: 'alert-info',
             spinnerClass: '',

             profile: 'en',
             profiles: [],

             training: false,

             unknownWords: []
         }
     },

     methods: {
         startSpinning: function() {
             this.spinnerClass = 'spinner'
         },

         stopSpinning: function() {
             this.spinnerClass = ''
         },

         clearAlert: function() {
             this.hasAlert = false
             this.alertText = ''
             this.alertClass = 'alert-info'
         },

         alert: function(text, level) {
             this.hasAlert = true
             this.alertText = text
             this.alertClass = 'alert-' + level
         },

         beginAsync: function() {
             this.clearAlert()
             this.startSpinning()
         },

         endAsync: function() {
             this.stopSpinning()
         },

         // Load profile names
         getProfiles: function() {
             ProfileService.getProfiles()
                           .then(request => {
                               this.profiles = request.data
                           })
                           .catch(err => this.alert(err.response.data, 'danger'))
         },

         train: function() {
             this.beginAsync()
             this.training = true
             LanguageModelService.train(this.profile)
                                 .then(request => this.alert(request.data, 'success'))
                                 .catch(err => this.alert(err.response.data, 'danger'))
                                 .then(() => {
                                     this.training = false
                                     this.getUnknownWords()
                                     this.endAsync()
                                 })
         },

         reload: function() {
             LanguageModelService.reload(this.profile)
                                 .then(request => this.alert(request.data, 'success'))
                                 .catch(err => this.alert(err.response.data, 'danger'))
         },

         getUnknownWords: function() {
             PronounceService.getUnknownWords(this.profile)
                             .then(request => {
                                 this.unknownWords = Object.entries(request.data)
                                 this.unknownWords.sort()
                             })
                             .catch(err => this.alert(err.response.data, 'danger'))
         }
     },

     mounted: function() {
         this.getProfiles()
         this.getUnknownWords()
     },

     watch: {
         profile() {
             this.getUnknownWords()
         }
     }
 }
</script>

<style>
 #app {
     font-family: 'Avenir', Helvetica, Arial, sans-serif;
     -webkit-font-smoothing: antialiased;
     -moz-osx-font-smoothing: grayscale;
     color: #2c3e50;
 }
</style>
