<template>
    <div class="container">
        <form class="form" v-on:submit.prevent="saveSettings">
            <div class="form-group">
                <div class="form-row text-muted pl-1">
                    <p>
                        This is a simplified interface to edit your <a href="https://rhasspy.readthedocs.io/en/latest/profiles/">your Rhasspy profile</a>. If you want to access the JSON directly, see the Advanced tab.
                    </p>
                </div>
                <div class="form-row pl-1">
                    <p><strong>Restart required if changes are made</strong></p>
                </div>
            </div>

            <button class="btn btn-primary">Save Settings</button>

            <div class="card mt-3">
                <div class="card-header"><i class="fas fa-crow"></i>Rhasspy</div>
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
                            <div class="col text-muted">
                                Profile that Rhasspy will load at startup and use unless told otherwise
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <input type="checkbox" id="wake-on-start" v-model="wakeOnStart">
                            <label for="wake-on-start" class="col-form-label">Listen for wake word on start-up</label>
                            <span class="col-form-label text-muted">(default profile)</span>
                        </div>
                    </div>
                    <hr>
                    <div class="form-group">
                        <div class="form-row">
                            <input type="checkbox" id="mqtt-enabled" v-model="mqttEnabled">
                            <label for="mqtt-enabled" class="col-form-label">Enable MQTT</label>
                            <span class="col-form-label text-muted">(<a href="https://docs.snips.ai/ressources/hermes-protocol">Snips.ai compatibility</a>)</span>
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
                            <label for="mqtt-siteid" class="col-form-label">Site ID</label>
                            <div class="col-sm-auto">
                                <input id="mqtt-siteid" type="text" class="form-control" v-model="mqttSiteId" :disabled="!mqttEnabled">
                            </div>
                            <div class="col text-muted">
                                Snips site name
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <input type="checkbox" id="mqtt-publish_intents" v-model="mqttPublishIntents" :disabled="!mqttEnabled">
                            <label for="mqtt-publish_intents" class="col-form-label">Publish intents over MQTT</label>
                        </div>
                        <div class="form-row">
                            <div class="col text-muted">
                                Intents will be published to <tt>hermes/intent/&lt;INTENT_NAME&gt;</tt>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <h2 class="mt-3">{{ this.profile }}</h2>

            <div class="card mt-3">
                <div class="card-header"><i class="fas fa-home"></i>Home Assistant</div>
                <div class="card-body">
                    <div class="form-group">
                        <div class="form-row">
                            <label for="hass-url" class="col-form-label">Hass URL</label>
                            <div class="col">
                                <input id="hass-url" type="text" class="form-control" v-model="hassURL">
                            </div>
                            <div class="col text-muted">
                                Address of your Home Assistant server
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="hass-token" class="col-form-label">Access Token</label>
                            <div class="col">
                                <input id="hass-token" type="text" class="form-control" v-model="hassToken">
                            </div>
                            <div class="col text-muted">
                                Long-lived access token (automatically filled in Hass.IO)
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="hass-password" class="col-form-label">API Password</label>
                            <div class="col">
                                <input id="hass-password" type="text" class="form-control" v-model="hassPassword">
                            </div>
                            <div class="col text-muted">
                                Home Assistant password (deprecated)
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <button class="btn btn-primary mt-3">Save Settings</button>

            <div class="card mt-3">
                <div class="card-header"><i class="fas fa-exclamation-circle"></i>Wake Word</div>
                <div class="card-body">
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="wake-system" id="dummy-wake" value="dummy" v-model="rhasspyWake">
                                <label class="form-check-label" for="dummy-wake">
                                    No wake word on this device
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="wake-system" id="pocketsphinx-wake" value="pocketsphinx" v-model="rhasspyWake">
                                <label class="form-check-label" for="pocketsphinx-wake">
                                    Use <a href="https://github.com/cmusphinx/pocketsphinx">Pocketsphinx</a> on this device
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="wake-keyphrase" class="col-form-label">Wake Keyphrase</label>
                            <div class="col-sm-auto">
                                <input id="wake-keyphrase" type="text" class="form-control" v-model="wakeKeyphrase" :disabled="rhasspyWake != 'pocketsphinx'">
                            </div>
                            <div class="col text-muted">
                                3-4 syllables recommended
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="wake-system" id="snowboy-wake" value="snowboy" v-model="rhasspyWake">
                                <label class="form-check-label" for="snowboy-wake">
                                    Use <a href="https://snowboy.kitt.ai">snowboy</a> on this device
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="snowboy-model" class="col-form-label">Model Name</label>
                            <div class="col-sm-auto">
                                <input id="snowboy-model" type="text" class="form-control" v-model="snowboyModel" :disabled="rhasspyWake != 'snowboy'">
                            </div>
                            <div class="col text-muted">
                                Put models in your profile directory
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="wake-system" id="precise-wake" value="precise" v-model="rhasspyWake">
                                <label class="form-check-label" for="precise-wake">
                                    Use <a href="https://github.com/MycroftAI/mycroft-precise">Mycroft Precise</a> on this device
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="precise-model" class="col-form-label">Model Name</label>
                            <div class="col-sm-auto">
                                <input id="precise-model" type="text" class="form-control" v-model="preciseModel" :disabled="rhasspyWake != 'precise'">
                            </div>
                            <div class="col text-muted">
                                Put models in your profile directory
                            </div>
                        </div>
                    </div>
                    <hr>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="wake-system" id="mqtt-wake" value="hermes" v-model="rhasspyWake">
                                <label class="form-check-label" for="mqtt-wake">
                                    Wake up on MQTT message (<a href="https://docs.snips.ai/ressources/hermes-protocol">Hermes protocol</a>)
                                </label>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="col text-muted">
                                Rhasspy will listen for a message on: <tt>hermes/hotword/{{ this.wakewordId }}/detected</tt>
                                <div class="alert alert-danger" v-if="rhasspyWake == 'hermes' && !mqttEnabled">
                                    MQTT is not enabled
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <button class="btn btn-primary mt-3">Save Settings</button>

            <div class="card mt-3">
                <div class="card-header"><i class="fas fa-phone-volume"></i>Speech Recognition</div>
                <div class="card-body">
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="stt-system" id="dummy-stt" value="dummy" v-model="rhasspySTT">
                                <label class="form-check-label" for="local-stt">
                                    No speech recognition on this device
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="stt-system" id="pocketsphinx-stt" value="pocketsphinx" v-model="rhasspySTT">
                                <label class="form-check-label" for="pocketsphinx-stt">
                                    Do speech recognition with <a href="https://github.com/cmusphinx/pocketsphinx">pocketsphinx</a> on this device
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
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
                                <input id="stt-url" type="text" class="form-control" v-model="sttURL" :disabled="rhasspySTT != 'remote'">
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="col text-muted">
                                Example: http://localhost:12101/api/speech-to-text
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <button class="btn btn-primary mt-3">Save Settings</button>

            <div class="card mt-3">
                <div class="card-header"><i class="fas fa-comment"></i>Intent Recognition</div>
                <div class="card-body">
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="intent-system" id="dummy-intent" value="dummy" v-model="rhasspyIntent">
                                <label class="form-check-label" for="dummy-intent">
                                    No intent recognition on this device
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="intent-system" id="fuzzywuzzy-intent" value="fuzzywuzzy" v-model="rhasspyIntent">
                                <label class="form-check-label" for="fuzzywuzzy-intent">
                                    Do intent recognition with <a href="https://github.com/seatgeek/fuzzywuzzy">fuzzywuzzy</a> on this device
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="intent-system" id="adapt-intent" value="adapt" v-model="rhasspyIntent">
                                <label class="form-check-label" for="adapt-intent">
                                    Do intent recognition with <a href="https://github.com/MycroftAI/adapt/">Mycroft Adapt</a> on this device
                                </label>
                            </div>
                        </div>
                    </div>
                    <hr>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="intent-system" id="rasa-intent" value="rasa" v-model="rhasspyIntent">
                                <label class="form-check-label" for="rasa-intent">
                                    Use remote <a href="https://rasa.com/docs/nlu/">RasaNLU</a> server
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="rasa-intent-url" class="col-form-label">RasaNLU URL</label>
                            <div class="col">
                                <input id="rasa-intent-url" type="text" class="form-control" v-model="rasaIntentURL" :disabled="rhasspyIntent != 'rasa'">
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="col text-muted">
                                Example: http://localhost:5000/
                            </div>
                        </div>
                    </div>
                    <hr>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="intent-system" id="remote-intent" value="remote" v-model="rhasspyIntent">
                                <label class="form-check-label" for="remote-intent">
                                    Use remote Rhasspy server
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <label for="remote-intent-url" class="col-form-label">Rhasspy Text-to-Intent URL</label>
                            <div class="col">
                                <input id="remote-intent-url" type="text" class="form-control" v-model="remoteIntentURL" :disabled="rhasspyIntent != 'remote'">
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="col text-muted">
                                Example: http://localhost:12101/api/text-to-intent
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <button class="btn btn-primary mt-3">Save Settings</button>

            <div class="card mt-3">
                <div class="card-header"><i class="fas fa-microphone"></i>Audio Recording</div>
                <div class="card-body">
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="audioSystem" id="audio-dummy" value="dummy" v-model="audioSystem">
                                <label class="form-check-label" for="audio-dummy">
                                    No recording on this device
                                </label>
                            </div>
                        </div>
                    </div>
                    <hr>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="audioSystem" id="audio-pyaudio" value="pyaudio" v-model="audioSystem" @click="getMicrophones('pyaudio')">
                                <label class="form-check-label" for="audio-pyaudio">
                                    Use PyAudio (default)
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="audioSystem" id="audio-arecord" value="arecord" v-model="audioSystem" @click="getMicrophones('arecord')">
                                <label class="form-check-label" for="audio-arecord">
                                    Use <tt>arecord</tt> directly (ALSA)
                                </label>
                            </div>
                        </div>
                        <div class="form-row text-muted">
                            <div class="col">
                                Requires <tt>alsa-utils</tt> to be installed
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="col-auto">
                                <label for="device" class="col-form-label col">Audio Device</label>
                            </div>
                            <div class="col-auto">
                                <select id="device" v-model="device"
                                        :disabled="testing || !(audioSystem == 'pyaudio' || audioSystem == 'arecord')">
                                    <option value="">Default Device</option>
                                    <option v-for="(desc, id) in microphones" :value="id" v-bind:key="id">{{ id }}: {{ desc }}</option>
                                </select>
                            </div>
                            <div class="col-auto">
                                <button type="button" class="btn btn-success"
                                        @click="testMicrophones"
                                        title="Test microphones and update the list"
                                        :disabled="testing || !(audioSystem == 'pyaudio' || audioSystem == 'arecord')">Test</button>
                            </div>
                        </div>
                    </div>
                    <hr>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="audioSystem" id="audio-mqtt" value="hermes" v-model="audioSystem">
                                <label class="form-check-label" for="audio-mqtt">
                                    Get microphone input remotely with MQTT (<a href="https://docs.snips.ai/ressources/hermes-protocol">Hermes protocol</a>)
                                </label>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="col text-muted">
                                Rhasspy will listen for WAV data on: <tt>hermes/audioServer/{{ this.mqttSiteId }}/audioFrame</tt>
                                <div class="alert alert-danger" v-if="audioSystem == 'hermes' && !mqttEnabled">
                                    MQTT is not enabled
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <button class="btn btn-primary mt-3">Save Settings</button>

            <div class="card mt-3">
                <div class="card-header"><i class="fas fa-volume-up"></i>Audio Playing</div>
                <div class="card-body">
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="soundSystem" id="sound-dummy" value="dummy" v-model="soundSystem">
                                <label class="form-check-label" for="sound-dummy">
                                    No playback on this device
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="soundSystem" id="sound-aplay" value="aplay" v-model="soundSystem">
                                <label class="form-check-label" for="sound-aplay">
                                    Use <tt>aplay</tt> directly (ALSA)
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-row">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="soundSystem" id="sound-mqtt" value="hermes" v-model="soundSystem">
                                <label class="form-check-label" for="sound-mqtt">
                                    Play sound remotely with MQTT (<a href="https://docs.snips.ai/ressources/hermes-protocol">Hermes protocol</a>)
                                </label>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="col text-muted">
                                Rhasspy will publish WAV data on: <tt>hermes/audioServer/{{ this.mqttSiteId }}/playBytes/&lt;REQUEST_ID&gt;</tt>
                                <div class="alert alert-danger" v-if="soundSystem == 'hermes' && !mqttEnabled">
                                    MQTT is not enabled
                                </div>
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

             rhasspySTT: '',
             sttURL: '',

             rhasspyIntent: '',
             rasaIntentURL: '',
             remoteIntentURL: '',

             rhasspyWake: '',
             snowboyModel: '',
             preciseModel: '',
             wakewordId: '',

             audioSystem: '',
             microphones: {},
             device: '',
             testing: false,

             soundSystem: '',

             wakeOnStart: false,
             wakeKeyphrase: '',

             mqttEnabled: false,
             mqttHost: '',
             mqttPort: 0,
             mqttUsername: '',
             mqttPassword: '',
             mqttSiteId: '',
             mqttPublishIntents: false
         }
     },

     methods: {
         loadSettings: function() {
             ProfileService.getProfileSettings('profile')
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
                               this.wakeOnStart = this._.get(this.profileSettings,
                                                             'rhasspy.listen_on_start',
                                                             this.defaultSettings.rhasspy.listen_on_start)

                               this.wakeKeyphrase = this._.get(this.profileSettings,
                                                               'wake.pocketsphinx.keyphrase',
                                                               this.defaultSettings.wake.pocketsphinx.keyphrase)

                               this.snowboyModel = this._.get(this.profileSettings,
                                                              'wake.snowboy.model',
                                                              this.defaultSettings.wake.snowboy.model)

                               this.preciseModel = this._.get(this.profileSettings,
                                                              'wake.precise.model',
                                                              this.defaultSettings.wake.precise.model)

                               this.rhasspyWake = this._.get(this.profileSettings,
                                                             'wake.system',
                                                             this.defaultSettings.wake.system)

                               this.wakewordId = this._.get(this.profileSettings,
                                                            'wake.hermes.wakeword_id',
                                                            this.defaultSettings.wake.hermes.wakeword_id)

                               // Speech
                               this.rhasspySTT = this._.get(this.profileSettings,
                                                            'speech_to_text.system',
                                                            this.defaultSettings.speech_to_text.system)

                               this.sttURL = this._.get(this.profileSettings,
                                                        'speech_to_text.remote.url',
                                                        this.defaultSettings.speech_to_text.remote.url)

                               // Intent
                               this.rhasspyIntent = this._.get(this.profileSettings,
                                                               'intent.system',
                                                               this.defaultSettings.intent.system)

                               this.rasaIntentURL = this._.get(this.profileSettings,
                                                               'intent.rasa.url',
                                                               this.defaultSettings.intent.rasa.url)

                               this.remoteIntentURL = this._.get(this.profileSettings,
                                                                 'intent.remote.url',
                                                                 this.defaultSettings.intent.remote.url)

                               // Microphone
                               this.audioSystem = this._.get(this.profileSettings,
                                                             'microphone.system',
                                                             this.defaultSettings.microphone.system)

                               var devicePath = 'microphone.' + this.audioSystem + '.device'
                               this.device = this._.get(this.profileSettings, devicePath,
                                                        this._.get(this.defaultSettings, devicePath, ''))

                               // Speakers
                               this.soundSystem = this._.get(this.profileSettings,
                                                             'sounds.system',
                                                             this.defaultSettings.sounds.system)

                               // MQTT
                               this.mqttEnabled = this._.get(this.profileSettings,
                                                             'mqtt.enabled',
                                                             this.defaultSettings.mqtt.enabled)

                               this.mqttHost = this._.get(this.profileSettings,
                                                          'mqtt.host',
                                                          this.defaultSettings.mqtt.host)

                               this.mqttPort = this._.get(this.profileSettings,
                                                          'mqtt.port',
                                                          this.defaultSettings.mqtt.port)

                               this.mqttUsername = this._.get(this.profileSettings,
                                                              'mqtt.username',
                                                              this.defaultSettings.mqtt.username)

                               this.mqttPassword = this._.get(this.profileSettings,
                                                              'mqtt.password',
                                                              this.defaultSettings.mqtt.password)

                               this.mqttSiteId = this._.get(this.profileSettings,
                                                            'mqtt.site_id',
                                                            this.defaultSettings.mqtt.site_id)

                               this.mqttPublishIntents = this._.get(this.profileSettings,
                                                                    'mqtt.publish_intents',
                                                                    this.defaultSettings.mqtt.publish_intents)
                           })
                           .catch(err => this.$parent.error(err))
         },

         refreshSettings: function() {
             ProfileService.getProfileSettings('defaults')
                           .then(request => {
                               this.defaultSettings = request.data
                               this.loadSettings()
                           })
                           .catch(err => this.$parent.error(err))
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

             // Speech recognition
             this._.set(this.profileSettings,
                        'speech_to_text.system',
                        this.rhasspySTT)

             this._.set(this.profileSettings,
                        'speech_to_text.remote.url',
                        this.sttURL)

             // Intent recognition
             this._.set(this.profileSettings,
                        'intent.system',
                        this.rhasspyIntent)

             this._.set(this.profileSettings,
                        'intent.rasa.url',
                        this.rasaIntentURL)

             this._.set(this.profileSettings,
                        'intent.remote.url',
                        this.remoteIntentURL)

             // Wake
             this._.set(this.profileSettings,
                        'rhasspy.listen_on_start',
                        this.wakeOnStart)

             this._.set(this.profileSettings,
                        'wake.system',
                        this.rhasspyWake)

             this._.set(this.profileSettings,
                        'wake.snowboy.model',
                        this.snowboyModel)

             this._.set(this.profileSettings,
                        'wake.precise.model',
                        this.preciseModel)

             this._.set(this.profileSettings,
                        'wake.pocketsphinx.keyphrase',
                        this.wakeKeyphrase)

             this._.set(this.profileSettings,
                        'wake.hermes.wakeword_id',
                        this.wakewordId)

             // Microphone
             this._.set(this.profileSettings,
                        'microphone.system',
                        this.audioSystem)

             this._.set(this.profileSettings,
                        'microphone.' + this.audioSystem + '.device',
                        this.device)

             // Speakers
             this._.set(this.profileSettings,
                        'sounds.system',
                        this.soundSystem)

             // MQTT
             this._.set(this.profileSettings,
                        'mqtt.enabled',
                        this.mqttEnabled)

             this._.set(this.profileSettings,
                        'mqtt.host',
                        this.mqttHost)

             this._.set(this.profileSettings,
                        'mqtt.password',
                        this.mqttPassword)

             this._.set(this.profileSettings,
                        'mqtt.username',
                        this.mqttUsername)

             this._.set(this.profileSettings,
                        'mqtt.password',
                        this.mqttPassword)

             this._.set(this.profileSettings,
                        'mqtt.site_id',
                        this.mqttSiteId)

             this._.set(this.profileSettings,
                        'mqtt.publish_intents',
                        this.mqttPublishIntents)

             // POST to server
             this.$parent.beginAsync()
             ProfileService.updateDefaultSettings(this.defaultSettings)
                 .then(() => {
                     ProfileService.updateProfileSettings(this.profileSettings)
                                   .then(request => this.$parent.alert(request.data, 'success'))
                                   .then(() => {
                                       this.$parent.endAsync()
                                   })
                                   .catch(err => this.$parent.error(err))
                 })
                 .catch(err => this.$parent.error(err))
         },

         testMicrophones: function() {
             this.testing = true
             this.$parent.beginAsync()
             ProfileService.testMicrophones(this.audioSystem)
                 .then(request => {
                     this.microphones = request.data

                     // Select default
                     for (var key in this.microphones) {
                         var value = this.microphones[key]
                         if (value.indexOf('*') >= 0) {
                             this.device = key
                         }
                     }

                     this.$parent.alert('Successfully tested microphones', 'success')
                 })
                 .then(() => {
                     this.testing = false
                     this.$parent.endAsync()
                 })
                 .catch(err => this.$parent.error(err))
         },

         getMicrophones: function(system) {
             ProfileService.getMicrophones(system)
                           .then(request => {
                               this.microphones = request.data

                               var devicePath = 'microphone.' + this.audioSystem + '.device'
                               this.device = this._.get(this.profileSettings, devicePath,
                                                        this._.get(this.defaultSettings, devicePath, ''))
                           })
                           .catch(err => this.$parent.error(err))
         }
     },

     mounted: function() {
         this.refreshSettings()
         this.getMicrophones()
     },

     watch: {
         profile() {
             this.refreshSettings()
         }
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
