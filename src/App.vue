<template>
    <div id="app">
        <!-- Top Bar -->
        <nav class="navbar navbar-expand-sm navbar-dark bg-dark fixed-top">
            <img class="navbar-brand" v-bind:class="spinnerClass" src="/img/logo.png">

            <button class="navbar-toggler" type="button" data-toggle="collapse" data-target="#navbarSupportedContent" aria-controls="navbarSupportedContent" aria-expanded="false" aria-label="Toggle navigation">
                <span class="navbar-toggler-icon"></span>
            </button>

            <div class="collapse navbar-collapse" id="navbarSupportedContent">
                <div class="navbar-container">
                    <a href="/" class="text-white font-weight-bold">Rhasspy</a>
                    <a href="/api/" class="badge badge-info ml-2">API</a>
                </div>
                <div class="navbar-container ml-auto">
                    <span title="Profile name" class="badge badge-primary ml-2" style="font-size: 1em">{{ this.profile.name }}</span>
                    <button class="btn btn-success ml-2" @click="train" :disabled="this.training" title="Re-train current profile">Train</button>
                    <button class="btn btn-warning ml-2" @click="wakeup" title="Make Rhasspy listen for a voice command">Wake</button>
                    <button class="btn btn-danger ml-2" @click="restart" :disabled="this.restarting" title="Restart Rhasspy server">Restart</button>
                </div>
            </div>
        </nav>
        <div class="main-container">
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
                <li class="nav-item">
                    <a class="nav-link" id="settings-tab" data-toggle="tab" href="#settings" role="tab" aria-controls="settings" aria-selected="true">Settings</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" id="advanced-tab" data-toggle="tab" href="#advanced" role="tab" aria-controls="advanced" aria-selected="true">Advanced</a>
                </li>
            </ul>
            <div class="tab-content" id="myTabContent">
                <div class="tab-pane fade show active" id="speech" role="tabpanel" aria-labelledby="speech-tab">
                    <TranscribeSpeech />
                </div>
                <div class="tab-pane fade" id="language" role="tabpanel" aria-labelledby="language-tab">
                    <TrainLanguageModel />
                </div>
                <div class="tab-pane fade" id="pronounce" role="tabpanel" aria-labelledby="pronounce-tab">
                    <LookupPronounce :unknownWords="unknownWords" />
                </div>
                <div class="tab-pane fade" id="settings" role="tabpanel" aria-labelledby="settings-tab">
                    <ProfileSettings :profile="profile" :profiles="profiles" :defaults="defaults"
                                     v-on:begin-async="beginAsync"
                                     v-on:end-async="endAsync"
                                     v-on:restart="restart"
                                     v-on:alert="alert($event.text, $event.level)"
                                     v-on:error="error($event)" />
                </div>
                <div class="tab-pane fade" id="advanced" role="tabpanel" aria-labelledby="advanced-tab">
                    <AdvancedSettings :profile="profile" :defaults="defaults" />
                </div>
            </div>

        </div> <!-- main container -->

        <div class="alert main-alert alert-dismissable" v-bind:class="alertClass" role="alert" v-if="hasAlert">
            <button type="button" class="close" aria-label="Close" @click="clearAlert">
                <span aria-hidden="true">&times;</span>
            </button>
            {{ this.alertText }}
        </div>

        <!-- Profile download modal -->
        <div class="modal fade" id="download-modal" tabindex="-1" role="dialog" aria-labelledby="downloadModalLabel" aria-hidden="true">
            <div class="modal-dialog" role="document">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="downloadModalLabel">Download Profile</h5>
                        <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                            <span aria-hidden="true">&times;</span>
                        </button>
                    </div>
                    <div class="modal-body">
                        <p>
                            Some files must be <a href="https://github.com/synesthesiam/rhasspy-profiles/releases">downloaded</a>
                            for your selected profile ({{ this.profile.name }}).
                        </p>
                        <p>
                            Rhasspy will not work correctly until these files are downloaded.
                            If you want to use a different profile, select it from the Settings page and click Restart.
                        </p>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-primary" @click="downloadProfile" :disabled="this.downloading">Download Now</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
 import ProfileService from '@/services/ProfileService'
 import TranscribeService from '@/services/TranscribeService'
 import LanguageModelService from '@/services/LanguageModelService'
 import PronounceService from '@/services/PronounceService'
 import RhasspyService from '@/services/RhasspyService'

 import LookupPronounce from './components/LookupPronounce.vue'
 import TrainLanguageModel from './components/TrainLanguageModel.vue'
 import TranscribeSpeech from './components/TranscribeSpeech.vue'
 import ProfileSettings from './components/ProfileSettings.vue'
 import AdvancedSettings from './components/AdvancedSettings.vue'

 import ProfileDefaults from '@/assets/ProfileDefaults'

 export default {
     name: 'app',
     components: {
         LookupPronounce,
         TrainLanguageModel,
         TranscribeSpeech,
         ProfileSettings,
         AdvancedSettings
     },

     data: function() {
         return {
             hasAlert: false,
             alertText: '',
             alertClass: 'alert-info',
             spinnerClass: '',

             profile: ProfileDefaults.profileDefaults,
             profiles: [],
             defaults: ProfileDefaults.profileDefaults,

             training: false,
             restarting: false,
             downloading: false,

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

         error: function(err) {
             this.alert(this._.get(err, 'response.data', err.toString()), 'danger')
         },

         // Load profile object
         getProfile: function() {
             ProfileService.getProfileSettings('all')
                           .then(request => {
                               this.profile = request.data
                           })
                           .catch(err => this.error(err))
         },

         // Load profile names
         getProfiles: function() {
             ProfileService.getProfiles()
                           .then(request => {
                               this.profiles = request.data.profiles
                               if (!request.data.downloaded) {
                                   $("#download-modal").modal()
                               }
                           })
                           .catch(err => this.error(err))
         },

         getDefaults: function() {
             ProfileService.getProfileSettings('defaults')
                           .then(request => {
                               this.defaults = request.data
                           })
                           .catch(err => this.error(err))
         },

         train: function() {
             this.beginAsync()
             this.training = true
             LanguageModelService.train()
                                 .then(request => this.alert(request.data, 'success'))
                                 .catch(err => this.error(err))
                                 .then(() => {
                                     this.training = false
                                     this.endAsync()
                                     this.getUnknownWords()
                                 })
         },

         restart: function() {
             this.beginAsync()
             this.restarting = true
             RhasspyService.restart()
                           .then(request => this.alert(request.data, 'success'))
                           .catch(err => this.error(err))
                           .then(() => {
                               this.restarting = false
                               this.training = false
                               this.endAsync()
                               window.location.reload()
                           })
         },

         getUnknownWords: function() {
             PronounceService.getUnknownWords()
                             .then(request => {
                                 this.unknownWords = Object.entries(request.data)
                                 this.unknownWords.sort()
                             })
                             .catch(err => this.error(err))
         },

         wakeup: function() {
             TranscribeService.wakeup()
         },

         downloadProfile: function() {
             this.beginAsync()
             this.downloading = true
             ProfileService.downloadProfile()
                 .then(() => {
                     this.restart()
                 })
                 .catch(err => this.error(err))
                 .then(() => {
                     this.downloading = false
                     this.endAsync()
                 })
         }
     },

     mounted: function() {
         this.getProfile()
         this.getProfiles()
         this.getDefaults()
         this.getUnknownWords()
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
