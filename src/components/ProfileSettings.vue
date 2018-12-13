<template>
    <div class="container">
        <form class="form" v-on:submit.prevent="saveSettings">
            <button class="btn btn-primary">Save Settings</button>

            <div class="card mt-3">
                <div class="card-header">Rhasspy</div>
                <div class="card-body">
                    <div class="form-group">
                        <div class="form-row">
                            <label for="default-profile" class="col-form-label">Default Profile</label>
                            <div class="col">
                                <select id="rhasspy-profiles" v-model="defaultProfile">
                                    <option disabled value="">Select Profile</option>
                                    <option v-for="profile in profiles" v-bind:key="profile">{{ profile }}</option>
                                </select>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <h2 class="mt-3">{{ this.profile }}</h2>

            <div class="card mt-3">
                <div class="card-header">Home Assistant</div>
                <div class="card-body">
                    <div class="form-group">
                        <div class="form-row">
                            <label for="hass-url" class="col-form-label">Hass URL</label>
                            <div class="col">
                                <input id="hass-url" type="text" class="form-control" v-model="hassURL">
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="hass-token" class="col-form-label">Access Token</label>
                            <div class="col">
                                <input id="hass-token" type="text" class="form-control" v-model="hassToken">
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="hass-password" class="col-form-label">API Password</label>
                            <div class="col">
                                <input id="hass-password" type="text" class="form-control" v-model="hassPassword">
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card mt-3">
                <div class="card-header">Speech Recognition</div>
                <div class="card-body">
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="localSTT" id="local-stt" value="local" v-model="rhasspySTT">
                                <label class="form-check-label" for="local-stt">
                                    Do speech recognition on this device
                                </label>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="remoteSTT" id="remote-stt" value="remote" v-model="rhasspySTT">
                                <label class="form-check-label" for="remote-stt">
                                    Use remote Rhasspy server for speech recognition
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="stt-url" class="col-form-label">Rhasspy Speech-to-Text URL</label>
                            <div class="col">
                                <input id="stt-url" type="text" class="form-control" v-model="sttURL" :disabled="rhasspySTT == 'local'">
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card mt-3">
                <div class="card-header">Intent Recognition</div>
                <div class="card-body">
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="localIntent" id="local-intent" value="local" v-model="rhasspyIntent">
                                <label class="form-check-label" for="local-intent">
                                    Do intent recognition on this device
                                </label>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="remoteIntent" id="remote-intent" value="remote" v-model="rhasspyIntent">
                                <label class="form-check-label" for="remote-intent">
                                    Use remote Rhasspy server for intent recognition
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="intent-url" class="col-form-label">Rhasspy Text-to-Intent URL</label>
                            <div class="col">
                                <input id="intent-url" type="text" class="form-control" v-model="intentURL" :disabled="rhasspyIntent == 'local'">
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <button class="btn btn-primary mt-3">Save Settings</button>

            <h2 class="mt-5">Current</h2>
            <div class="card">
                <div class="card-header">
                    Current settings for {{ this.profile }}
                </div>
                <div class="card-body">
                    <tree-view :data="profileSettings"
                               :options='{ rootObjectKey: "current" }'
                               :hidden="!profileSettings"></tree-view>
                </div>
            </div>

            <h2 class="mt-5">Defaults</h2>
            <div class="card">
                <div class="card-header">
                    Default settings for all profiles
                </div>
                <div class="card-body">
                    <tree-view :data="defaultSettings"
                               :options='{ rootObjectKey: "defaults" }'
                               :hidden="!defaultSettings"></tree-view>
                </div>
            </div>
        </form>
    </div> <!-- container -->
</template>

<script>
 import ProfileService from '@/services/ProfileService'

 export default {
     name: 'ProfileSettings',
     props: {
         profile : String,
         profiles: Array
     },
     data: function () {
         return {
             profileSettings: {},
             defaultSettings: {},

             defaultProfile: '',

             hassURL: '',
             hassToken: '',
             hassPassword: '',

             rhasspySTT: 'local',
             sttURL: '',

             rhasspyIntent: 'local',
             intentURL: ''
         }
     },

     methods: {
         refreshSettings: function() {
             ProfileService.getProfileSettings(this.profile, 'profile')
                           .then(request => {
                               this.profileSettings = request.data
                               this.defaultProfile = this._.get(this.profileSettings,
                                                                'rhasspy.default_profile',
                                                                this.defaultSettings.rhasspy.default_profile)

                               this.hassURL = this._.get(this.profileSettings,
                                                         'home_assistant.url',
                                                         this.defaultSettings.home_assistant.url)
                               this.hassPassword = this._.get(this.profileSettings,
                                                              'home_assistant.api_password',
                                                              this.defaultSettings.home_assistant.api_password)

                               this.hassToken = this._.get(this.profileSettings,
                                                           'home_assistant.access_token',
                                                           this.defaultSettings.home_assistant.access_token)

                               // Speech
                               var sttSystem = this._.get(this.profileSettings,
                                                          'speech_to_text.system',
                                                          this.defaultSettings.speech_to_text.system)

                               this.sttRemote = (sttSystem == 'remote') ? 'remote' : 'local'

                               this.sttURL = this._.get(this.profileSettings,
                                                        'speech_to_text.remote.url',
                                                        this.defaultSettings.speech_to_text.remote.url)

                               // Intent
                               var intentSystem = this._.get(this.profileSettings,
                                                          'intent.system',
                                                          this.defaultSettings.intent.system)

                               this.intentRemote = (intentSystem == 'remote') ? 'remote' : 'local'
                               this.intentURL = this._.get(this.profileSettings,
                                                        'intent.remote.url',
                                                        this.defaultSettings.intent.remote.url)
                           })
                           .catch(err => this.$parent.alert(err.response.data, 'danger'))
         },

         refreshDefaults: function() {
             ProfileService.getProfileSettings(this.profile, 'defaults')
                           .then(request => {
                               this.defaultSettings = request.data
                           })
                           .catch(err => this.$parent.alert(err.response.data, 'danger'))
         },

         saveSettings: function() {
             // Update settings
             this._.set(this.defaultSettings,
                        'rhasspy.default_profile',
                        this.defaultProfile)

             this._.set(this.profileSettings,
                        'home_assistant.url',
                        this.hassURL)

             this._.set(this.profileSettings,
                        'home_assistant.api_password',
                        this.hassPassword)

             this._.set(this.profileSettings,
                        'home_assistant.access_token',
                        this.hassToken)

             if (this.rhasspySTT == 'remote') {
                 // Remote speech to text
                 this._.set(this.profileSettings,
                            'speech_to_text.system',
                            'remote')

                 this._.set(this.profileSettings,
                            'speech_to_text.remote.url',
                            this.sttURL)
             } else {
                 // Local speech to text
                 this._.set(this.profileSettings,
                            'speech_to_text.system',
                            this._.get(this.defaultSettings,
                                       'speech_to_text.system',
                                       'pocketsphinx'))
             }

             if (this.rhasspyIntent == 'remote') {
                 // Remote intent recognition
                 this._.set(this.profileSettings,
                            'intent.system',
                            'remote')

                 this._.set(this.profileSettings,
                            'intent.remote.url',
                            this.intentURL)
             } else {
                 // Local intent recognition
                 this._.set(this.profileSettings,
                            'intent.system',
                            this._.get(this.defaultSettings,
                                       'intent.system',
                                       'fuzzywuzzy'))
             }

             // POST to server
             this.$parent.beginAsync()
             ProfileService.updateDefaultSettings(this.defaultSettings)
                 .catch(err => this.$parent.alert(err.response.data, 'danger'))
                 .then(() => {
                     ProfileService.updateProfileSettings(this.profile, this.profileSettings)
                                   .then(request => this.$parent.alert(request.data, 'success'))
                                   .catch(err => this.$parent.alert(err.response.data, 'danger'))
                                   .then(() => {
                                       this.$parent.endAsync()
                                   })
                 })
         }
     },

     mounted: function() {
         this.refreshDefaults()
         this.refreshSettings()
     },

     watch: {
         profile() {
             this.refreshDefaults()
             this.refreshSettings()
         }
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
