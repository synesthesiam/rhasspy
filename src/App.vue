<template>
    <div id="app">
        <!-- Top Bar -->
        <nav class="navbar navbar-expand-sm navbar-dark bg-dark fixed-top">
            <a href="/">
                <img id="logo" class="navbar-brand" v-bind:class="spinnerClass" src="/img/logo.png">
            </a>

            <button class="navbar-toggler" type="button" data-toggle="collapse" data-target="#navbarSupportedContent" aria-controls="navbarSupportedContent" aria-expanded="false" aria-label="Toggle navigation">
                <span class="navbar-toggler-icon"></span>
            </button>

            <div class="collapse navbar-collapse" id="navbarSupportedContent">
                <div class="navbar-container">
                    <a href="/" class="text-white font-weight-bold">Rhasspy</a>
                    <a href="/api/" class="badge badge-info ml-2">{{ this.version }}</a>
                    <span class="badge badge-pill badge-danger ml-2" v-if="this.numProblems > 0" title="Problems were detected"><i class="fas fa-exclamation"></i></span>
                </div>
                <div class="navbar-container ml-auto">
                    <span title="Profile name" class="badge badge-primary ml-2" style="font-size: 1em">{{ this.profile.name }}</span>
                    <div class="btn-group">
                        <button class="btn btn-success ml-2" @click="train(false)" :disabled="this.training" title="Re-train current profile">Train</button>
                        <button type="button" class="btn btn-success dropdown-toggle dropdown-toggle-split" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
                            <span class="sr-only">Toggle Dropdown</span>
                        </button>
                        <div class="dropdown-menu">
                            <a class="dropdown-item" href="#" @click="train(true)">Clear Cache</a>
                        </div>
                    </div>

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
                    <a class="nav-link" id="slots-tab" data-toggle="tab" href="#slots" role="tab" aria-controls="pronounce" aria-selected="true">Slots</a>
                <li class="nav-item">
                    <a class="nav-link" id="pronounce-tab" data-toggle="tab" href="#pronounce" role="tab" aria-controls="pronounce" aria-selected="true">Words</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" id="settings-tab" data-toggle="tab" href="#settings" role="tab" aria-controls="settings" aria-selected="true">Settings</a>
                </li>
                <li class="nav-item" v-if="this.numProblems > 0">
                    <a class="nav-link" id="problems-tab" data-toggle="tab" href="#problems" role="tab" aria-controls="problems" aria-selected="true">Problems <span class="badge badge-pill badge-danger">{{ this.numProblems }}</span></a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" id="advanced-tab" data-toggle="tab" href="#advanced" role="tab" aria-controls="advanced" aria-selected="true">Advanced</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" id="log-tab" data-toggle="tab" href="#log" role="tab" aria-controls="log" aria-selected="true">Log</a>
                </li>
            </ul>
            <div class="tab-content" id="myTabContent">
                <div class="tab-pane fade show active" id="speech" role="tabpanel" aria-labelledby="speech-tab">
                    <TranscribeSpeech />
                </div>
                <div class="tab-pane fade" id="language" role="tabpanel" aria-labelledby="language-tab">
                    <TrainLanguageModel />
                </div>
                <div class="tab-pane fade" id="slots" role="tabpanel" aria-labelledby="slots-tab">
                    <Slots />
                </div>
                <div class="tab-pane fade" id="pronounce" role="tabpanel" aria-labelledby="pronounce-tab">
                    <LookupPronounce :unknownWords="unknownWords" :customWords="customWords" />
                </div>
                <div class="tab-pane fade" id="settings" role="tabpanel" aria-labelledby="settings-tab">
                    <ProfileSettings :profile="profile" :profiles="profiles" :defaults="defaults"
                                     v-on:begin-async="beginAsync"
                                     v-on:end-async="endAsync"
                                     v-on:restart="restart"
                                     v-on:alert="alert($event.text, $event.level)"
                                     v-on:error="error($event)" />
                </div>
                <div class="tab-pane fade" id="problems" role="tabpanel" aria-labelledby="problems-tab">
                    <Problems :problems="problems" />
                </div>
                <div class="tab-pane fade" id="log" role="tabpanel" aria-labelledby="log-tab">
                    <RhasspyLog :rhasspyLog="rhasspyLog" />
                </div>
                <div class="tab-pane fade" id="advanced" role="tabpanel" aria-labelledby="advanced-tab">
                    <AdvancedSettings />
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
            <div class="modal-dialog modal-lg" role="document">
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
                        </p>
                        <tree-view :data="missingFiles" :options="{ rootObjectKey: 'missing'}"></tree-view>
                        <br>
                        <label for="downloadStatus">Status:</label>
                        <textarea id="downloadStatus" v-model="this.downloadStatus" style="width: 100%;" rows="3"></textarea>
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
 import Problems from './components/Problems.vue'
 import RhasspyLog from './components/RhasspyLog.vue'
 import Slots from './components/Slots.vue'
 import AdvancedSettings from './components/AdvancedSettings.vue'

 import ProfileDefaults from '@/assets/ProfileDefaults'

 export default {
     name: 'app',
     components: {
         LookupPronounce,
         TrainLanguageModel,
         TranscribeSpeech,
         ProfileSettings,
         Problems,
         RhasspyLog,
         Slots,
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

             customWords: '',
             unknownWords: [],

             rhasspyLog: '',

             problems: {},
             numProblems: 0,

             missingFiles: {},

             version: '',

             downloadStatus: '',

             wakeSocket: null
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

             // Hide alert after 20 seconds
             setTimeout(this.clearAlert, 20000)
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
                               this.missingFiles = {}
                               if (!request.data.downloaded) {
                                   this.missingFiles = request.data.missing_files
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

         train: function(noCache) {
             this.beginAsync()
             this.training = true
             LanguageModelService.train(noCache)
                                 .then(this.getUnknownWords())
                                 .then(request => {
                                     if (this.unknownWords.length > 0) {
                                         this.alert('There are ' + this.unknownWords.length + ' unknown word(s)', 'warning')
                                     } else {
                                         this.alert(request.data, 'success')
                                     }
                                 })
                                 .catch(err => this.error(err))
                                 .then(() => {
                                     this.training = false
                                     this.endAsync()
                                     this.getCustomWords()
                                     this.getProblems()
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

         getCustomWords: function() {
             PronounceService.getCustomWords()
                             .then(request => {
                                 this.customWords = request.data
                             })
                             .catch(err => this.error(err))
         },

         getProblems: function() {
             RhasspyService.getProblems()
                           .then(request => {
                               this.problems = request.data
                               this.numProblems = 0
                               for (var actor in this.problems) {
                                   this.numProblems += Object.keys(this.problems[actor]).length
                               }
                           })
                           .catch(err => this.error(err))
         },

         getVersion: function() {
             RhasspyService.getVersion()
                             .then(request => {
                                 this.version = request.data
                             })
                             .catch(err => this.error(err))
         },

         wakeup: function() {
             TranscribeService.wakeup()
         },

         downloadProfile: function() {
             this.beginAsync()
             this.downloading = true
             this.downloadStatus = ''
             setTimeout(this.updateDownloadStatus, 1000)
             ProfileService.downloadProfile()
                 .then(() => {
                     alert("Download is complete. Rhasspy will now restart. Make sure to train before using your profile!")
                     this.restart()
                 })
                 .catch(err => this.error(err))
                 .then(() => {
                     this.downloading = false
                     this.endAsync()
                 })
         },

         updateDownloadStatus: function() {
             ProfileService.downloadStatus()
                .then((request) => {
                    this.downloadStatus = request.data
                })

             if (this.downloading) {
                 setTimeout(this.updateDownloadStatus, 1000)
             }
         },

         connectWakeSocket: function() {
             // Connect to /api/events/intent websocket
             var wsProtocol = 'ws://'
             if (window.location.protocol == 'https:') {
                 wsProtocol = 'wss://'
             }

             var wsURL = wsProtocol + window.location.host + '/api/events/wake'
             this.wakeSocket = new WebSocket(wsURL)
             this.wakeSocket.onmessage = (evt) => {
                 $('#logo').css('filter', 'invert()')
                 setTimeout(() => {
                     $('#logo').css('filter', 'initial')
                 }, 2000)
             }
             this.wakeSocket.onclose = () => {
                 // Try to reconnect
                 setTimeout(this.connectWakeSocket, 1000)
             }
         }
     },

     mounted: function() {
         this.getVersion()
         this.getProfile()
         this.getProfiles()
         this.getDefaults()
         this.getCustomWords()
         this.getUnknownWords()
         this.getProblems()
         this.connectWakeSocket()
         this.$options.sockets.onmessage = function(event) {
             this.rhasspyLog = event.data + '\n' + this.rhasspyLog
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
