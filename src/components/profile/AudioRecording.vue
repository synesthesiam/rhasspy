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
                            Get microphone input remotely with MQTT (<a href="https://docs.snips.ai/reference/hermes">Hermes protocol</a>)
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
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="profile.microphone.system" id="audio-system-http" value="http" v-model="profile.microphone.system">
                        <label class="form-check-label" for="audio-system-http">
                            Get microphone input remotely with HTTP (assumes <a href="https://en.wikipedia.org/wiki/Chunked_transfer_encoding">chunked transfer encoding</a>)
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="microphone-http-host" class="col-form-label">Host</label>
                    <div class="col-sm-auto">
                        <input id="microphone-http-host" type="text" class="form-control" v-model="profile.microphone.http.host" :disabled="profile.microphone.system != 'http'">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="microphone-http-port" class="col-form-label">Port</label>
                    <div class="col-sm-auto">
                        <input id="microphone-http-port" type="text" class="form-control" v-model="profile.microphone.http.port" :disabled="profile.microphone.system != 'http'">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="microphone-http-stop-never" id="microphone-http-stop-never" value="never" v-model="profile.microphone.http.stop_after">
                        <label class="form-check-label" :disabled="profile.microphone.system != 'http'" for="microphone-http-stop-never">
                            Stream Forever
                        </label>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="microphone-http-stop-text" id="microphone-http-stop-text" value="text" v-model="profile.microphone.http.stop_after">
                        <label class="form-check-label" :disabled="profile.microphone.system != 'http'" for="microphone-http-stop-text">
                            Stop After Speech Transcription
                        </label>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="microphone-http-stop-intent" id="microphone-http-stop-intent" value="intent" v-model="profile.microphone.http.stop_after">
                        <label class="form-check-label" :disabled="profile.microphone.system != 'http'" for="microphone-http-stop-intent">
                            Stop After Intent Recognition
                        </label>
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="profile.microphone.system" id="audio-system-gstreamer" value="gstreamer" v-model="profile.microphone.system">
                        <label class="form-check-label" for="audio-system-gstreamer">
                            Get microphone input from a <a href="https://gstreamer.freedesktop.org/">GStreamer pipeline</a>
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label class="form-label" for="gstreamer-pipeline">Pipeline</label>
                    <div class="col">
                        <textarea id="gstreamer-pipeline" class="form-control" type="text" rows="3" v-model="profile.microphone.gstreamer.pipeline" :disabled="profile.microphone.system != 'gstreamer'"></textarea>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <p class="text-muted">Keep pipeline on a single line. Rhasspy will run the following command:</p>
                </div>
                <div class="form-row">
                    <p class="text-muted">
                        <tt>gst-launch-1.0 {{ profile.microphone.gstreamer.pipeline }} ! fdsink fd=1</tt>
                    </p>
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
         device: {
            get: function() {
                if(this.profile.microphone[this.profile.microphone.system]) {
                    return this.profile.microphone[this.profile.microphone.system].device;
                }
                return "";
            },
            set: function(newValue) {
                this.profile.microphone[this.profile.microphone.system].device = newValue;
            }
         }
     },

     mounted: function() {
         this.getMicrophones();
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
