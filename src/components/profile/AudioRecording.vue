<template>
    <div class="card mt-3">
        <div class="card-header"><i class="fas fa-microphone"></i>Audio Recording</div>
        <div class="card-body">
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="microphone-system" id="audio-system-dummy" value="dummy" v-model="profile.microphone.system">
                        <label class="form-check-label" v-bind:class="{ 'text-danger': profile.microphone.system == 'dummy' }" for="audio-system-dummy">
                            No recording on this device
                        </label>
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="microphone-system" id="audio-system-pyaudio" value="pyaudio" v-model="profile.microphone.system" @click="getMicrophones('pyaudio')">
                        <label class="form-check-label" for="audio-system-pyaudio">
                            Use PyAudio (default)
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="microphone-system" id="audio-system-arecord" value="arecord" v-model="profile.microphone.system" @click="getMicrophones('arecord')">
                        <label class="form-check-label" for="audio-system-arecord">
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
                        <label for="device" class="col-form-label col">Input Device</label>
                    </div>
                    <div class="col-auto">
                        <select id="device" v-model="device"
                                :disabled="testing || !(profile.microphone.system == 'pyaudio' || profile.microphone.system == 'arecord')">
                            <option value="">Default Device</option>
                            <option v-for="(desc, id) in microphones" :value="id" v-bind:key="id">{{ id }}: {{ desc }}</option>
                        </select>
                    </div>
                    <div class="col-auto">
                        <button type="button" class="btn btn-success"
                                @click="testMicrophones"
                                title="Test microphones and update the list"
                                :disabled="testing || !(profile.microphone.system == 'pyaudio' || profile.microphone.system == 'arecord')">Test</button>
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="profile.microphone.system" id="audio-system-mqtt" value="hermes" v-model="profile.microphone.system">
                        <label class="form-check-label" for="audio-system-mqtt">
                            Get microphone input remotely with MQTT (<a href="https://docs.snips.ai/ressources/hermes-protocol">Hermes protocol</a>)
                        </label>
                    </div>
                </div>
                <div class="form-row">
                    <div class="col text-muted">
                        Rhasspy will listen for WAV data on: <tt>hermes/audioServer/{{ this.profile.mqtt.site_id }}/audioFrame</tt>
                        <div class="alert alert-danger" v-if="profile.microphone.system == 'hermes' && !profile.mqtt.enabled">
                            MQTT is not enabled
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
 import ProfileService from '@/services/ProfileService'

 export default {
     name: 'AudioRecording',
     props: {
         profile : Object
     },
     data: function () {
         return {
             device: '',
             microphones: {},
             testing: false
         }
     },

     methods: {
         testMicrophones: function() {
             this.testing = true
             this.$emit('begin-async')
             ProfileService.testMicrophones(this.profile.microphone.system)
                 .then(request => {
                     this.microphones = request.data

                     // Select default
                     for (var key in this.microphones) {
                         var value = this.microphones[key]
                         if (value.indexOf('*') >= 0) {
                             this.device = key
                         }
                     }

                     this.$emit('alert', {
                         text: 'Successfully tested microphones',
                         level: 'success'
                     })
                 })
                 .then(() => {
                     this.testing = false
                     this.$emit('end-async')
                 })
                 .catch(err => this.$emit('error', err))
         },

         getMicrophones: function(system) {
             ProfileService.getMicrophones(system)
                           .then(request => {
                               this.microphones = request.data
                           })
                           .catch(err => this.$emit('error', err))
         }
     },

     computed: {
         devicePath: function() {
             return 'microphone.' + this.profile.microphone.system + '.device'
         }
     },

     mounted: function() {
         this.getMicrophones()
         this.device = this._.get(this.profile, this.devicePath, '')
     },

     watch: {
         device: function() {
             this._.set(this.profile, this.devicePath, this.device)
         }
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
