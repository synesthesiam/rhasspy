<template>
    <div class="container">
        <form class="form" v-on:submit.prevent="saveSettings">
            <div class="form-group">
                <div class="form-row text-muted pl-1">
                    <p>
                        This is a simplified interface to edit your <a href="https://github.com/synesthesiam/rhasspy-hassio-addon/blob/master/doc/profiles.md">your Rhasspy profile</a>. If you want to access the JSON directly, see the Advanced tab.
                    </p>
                </div>
                <div class="form-row pl-1">
                    <p><strong>Restart required if changes are made</strong></p>
                </div>
            </div>

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
                <div class="card-header">Wake Word</div>
                <div class="card-body">
                    <div class="form-group">
                        <div class="form-row">
                            <input type="checkbox" id="wake-on-start" v-model="wakeOnStart">
                            <label for="wake-on-start" class="col-form-label">Listen for wake word on start-up</label>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="wake-system" id="local-wake" value="local" v-model="rhasspyWake">
                                <label class="form-check-label" for="local-wake">
                                    Use pocketsphinx locally
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="wake-keyphrase" class="col-form-label">Wake Keyphrase</label>
                            <div class="col-sm-auto">
                                <input id="wake-keyphrase" type="text" class="form-control" v-model="wakeKeyphrase" :disabled="rhasspyWake != 'local'">
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="wake-system" id="remote-wake" value="remote" v-model="rhasspyWake">
                                <label class="form-check-label" for="remote-wake">
                                    Use remote MQTT system (snowboy, precise)
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="wake-pub" class="col-form-label">Wakeword Id</label>
                            <div class="col-sm-auto">
                                <input id="wake-id" type="text" class="form-control" v-model="wakeId" :disabled="rhasspyWake != 'remote'">
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
                                <input class="form-check-input" type="radio" name="stt-system" id="local-stt" value="local" v-model="rhasspySTT">
                                <label class="form-check-label" for="local-stt">
                                    Do speech recognition on this device
                                </label>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="stt-system" id="remote-stt" value="remote" v-model="rhasspySTT">
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

            <div class="card mt-3">
                <div class="card-header">Audio Recording</div>
                <div class="card-body">
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="audioSystem" id="audio-pyaudio" value="pyaudio" v-model="audioSystem">
                                <label class="form-check-label" for="audio-pyaudio">
                                    Use PyAudio
                                </label>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="audioSystem" id="audio-arecord" value="arecord" v-model="audioSystem">
                                <label class="form-check-label" for="audio-arecord">
                                    Use arecord
                                </label>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="audioSystem" id="audio-mqtt" value="hermes" v-model="audioSystem">
                                <label class="form-check-label" for="audio-mqtt">
                                    Use MQTT
                                </label>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card mt-3">
                <div class="card-header">MQTT Configuration</div>
                <div class="card-body">
                    <div class="form-group">
                        <div class="form-row">
                            <input type="checkbox" id="mqtt-enabled" v-model="mqttEnabled">
                            <label for="mqtt-enabled" class="col-form-label">Enable MQTT</label>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="mqtt-host" class="col-form-label">Host</label>
                            <div class="col-sm-auto">
                                <input id="mqtt-host" type="text" class="form-control" v-model="mqttHost" :disabled="!mqttEnabled">
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="mqtt-port" class="col-form-label">Port</label>
                            <div class="col-sm-auto">
                                <input id="mqtt-port" type="text" class="form-control" v-model="mqttPort" :disabled="!mqttEnabled">
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="mqtt-username" class="col-form-label">Username</label>
                            <div class="col-sm-auto">
                                <input id="mqtt-username" type="text" class="form-control" v-model="mqttUsername" :disabled="!mqttEnabled">
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="mqtt-password" class="col-form-label">Password</label>
                            <div class="col-sm-auto">
                                <input id="mqtt-password" type="text" class="form-control" v-model="mqttPassword" :disabled="!mqttEnabled">
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="mqtt-siteid" class="col-form-label">Site ID (Hermes)</label>
                            <div class="col-sm-auto">
                                <input id="mqtt-siteid" type="text" class="form-control" v-model="mqttSiteId" :disabled="!mqttEnabled">
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
             intentURL: '',

             rhasspyWake: 'local',
             wakeId: '',

             audioSystem: 'pyaudio',

             wakeOnStart: false,
             wakeKeyphrase: '',

             mqttEnabled: false,
             mqttHost: '',
             mqttPort: 0,
             mqttUsername: '',
             mqttPassword: '',
             mqttSiteId: ''
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

                               // Wake
                               this.wakeOnStart = this._.get(this.defaultSettings,
                                                             'rhasspy.listen_on_start',
                                                             false)

                               this.wakeKeyphrase = this._.get(this.profileSettings,
                                                               'wake.pocketsphinx.keyphrase',
                                                               this.defaultSettings.wake.pocketsphinx.keyphrase)

                               this.wakeId = this._.get(this.profileSettings,
                                                        'wake.hermes.wakeword_id',
                                                        this.defaultSettings.wake.hermes.wakeword_id)

                               var wakeSystem = this._.get(this.profileSettings,
                                                           'wake.system',
                                                           this.defaultSettings.wake.system)

                               this.rhasspyWake = (wakeSystem == 'hermes') ? 'remote' : 'local'


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

                               // Microphone
                               this.audioSystem = this._.get(this.profileSettings,
                                                             'microphone.system',
                                                             this.defaultSettings.microphone.system)

                               // MQTT
                               this.mqttEnabled = this._.get(this.defaultSettings,
                                                             'mqtt.enabled',
                                                             false)

                               this.mqttHost = this._.get(this.defaultSettings,
                                                          'mqtt.host',
                                                          'localhost')

                               this.mqttPort = this._.get(this.defaultSettings,
                                                          'mqtt.port',
                                                          1883)

                               this.mqttUsername = this._.get(this.defaultSettings,
                                                              'mqtt.username',
                                                              '')

                               this.mqttPassword = this._.get(this.defaultSettings,
                                                              'mqtt.password',
                                                              '')

                               this.mqttSiteId = this._.get(this.defaultSettings,
                                                            'mqtt.site_id',
                                                            'default')
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

             // Wake
             this._.set(this.defaultSettings,
                        'rhasspy.listen_on_start',
                        this.wakeOnStart)

             if (this.rhasspyWake == 'remote') {
                 // Remote wake word
                 this._.set(this.profileSettings,
                            'wake.system',
                            'hermes')

                 this._.set(this.profileSettings,
                            'wake.hermes.wakeword_id',
                            this.wakeId)
             } else {
                 // Local wake word
                 this._.set(this.profileSettings,
                            'wake.system',
                            'pocketsphinx')

                 this._.set(this.profileSettings,
                            'wake.pocketsphinx.keyphrase',
                            this.wakeKeyphrase)
             }


             // Microphone
             this._.set(this.profileSettings,
                        'microphone.system',
                        this.audioSystem)

             // MQTT
             this._.set(this.defaultSettings,
                        'mqtt.enabled',
                        this.mqttEnabled)

             this._.set(this.defaultSettings,
                        'mqtt.host',
                        this.mqttHost)

             this._.set(this.defaultSettings,
                        'mqtt.password',
                        this.mqttPassword)

             this._.set(this.defaultSettings,
                        'mqtt.username',
                        this.mqttUsername)

             this._.set(this.defaultSettings,
                        'mqtt.password',
                        this.mqttPassword)

             this._.set(this.defaultSettings,
                        'mqtt.site_id',
                        this.mqttSiteId)

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
