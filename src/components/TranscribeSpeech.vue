<template>
    <div class="container">
        <form class="form" v-on:submit.prevent="getIntent">
            <div class="form-group">
                <div class="form-row text-muted">
                    <p>Press "Hold to Record", speak a command, then release</p>
                </div>
                <div class="form-row">
                    <div class="col-auto">
                        <button type="button" class="btn"
                                v-bind:class="{ 'btn-danger': holdRecording, 'btn-primary': !holdRecording }"
                                @mousedown="startRecording" @mouseup="stopRecording"
                                title="Record a voice command while held, interpret when released"
                                :disabled="interpreting || tapRecording">{{ holdRecording ? 'Release to Stop' : 'Hold to Record' }}</button>
                    </div>
                    <div class="col-auto">
                        <button type="button" class="btn"
                                v-bind:class="{ 'btn-danger': tapRecording, 'btn-success': !tapRecording }"
                                @click="toggleRecording"
                                title="Record a voice command while held, interpret when released"
                                :disabled="interpreting || (holdRecording && !tapRecording)">{{ tapRecording ? 'Tap to Stop' : 'Tap to Record' }}</button>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <div class="col">
                        <input type="radio" name="microphone" id="rhasspy-microphone" value="rhasspy" v-model="microphone">
                        <label class="ml-2" for="rhasspy-microphone">
                            <i class="fas fa-crow"></i>
                            Use Rhasspy microphone
                        </label>
                    </div>
                    <div class="col">
                        <input type="radio" name="microphone" id="browser-microphone" value="browser" v-model="microphone"
                               @click="getMicrophonePermission">
                        <label class="ml-2" for="browser-microphone">
                            <i class="fas fa-laptop"></i>
                            Use browser microphone
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <div class="col-auto">
                        <label for="wavFile" class="col-form-label col">WAV file</label>
                    </div>
                    <div class="col">
                        <input id="wavFile" ref="wavFile" type="file" class="form-control">
                    </div>
                    <div class="col-auto">
                        <button type="button" class="btn btn-info" @click="transcribe"
                                title="Upload and process a WAV file with a voice command">Transcribe WAV</button>
                    </div>
                </div>
                <div class="form-row">
                    <p class="text-muted mt-1">
                        16-bit 16Khz mono preferred
                    </p>
                </div>
            </div>

            <div class="form-group">
                <div class="form-row">
                    <div class="col-auto">
                        <label for="sentence" class="col-form-label col">Sentence</label>
                    </div>
                    <div class="col">
                        <input id="sentence" type="text" class="form-control" v-model="sentence">
                    </div>
                    <div class="col-auto">
                        <button type="button" class="btn btn-dark"
                                @click="saySentence"
                                title="Speak the sentence using Rhasspy's text to speech system">Speak</button>
                    </div>
                    <div class="col-auto">
                        <button type="submit" class="btn btn-secondary"
                                title="Send a text command as if it were spoken">Get Intent</button>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row mt-3">
                    <div class="col-auto">
                        <input type="checkbox" id="sendHass" v-model="sendHass"
                               title="If checked, forward all recognized intents to Home Assistant">
                        <label class="ml-1" for="sendHass">Send to Home Assistant</label>
                    </div>
                </div>
            </div>
            <hr />
            <div class="form-group mt-1" v-if="jsonSource != null">
                <div class="form-row" v-if="jsonSource.intent.name.length > 0">
                    <div class="badge badge-danger">{{ jsonSource.intent.name }}</div>
                </div>
                <div class="form-row" v-if="jsonSource.intent.name.length > 0">
                    <ul class="mt-1">
                        <li v-for="(value, key) in jsonSource.slots">{{ value }} <span class="badge badge-primary">{{ key }}</span></li>
                    </ul>
                </div>
                <div class="form-row mt-3">
                    <div>
                        <p class="text-muted mb-2">Raw Intent JSON</p>
                        <tree-view :data="jsonSource"
                                   :options='{ rootObjectKey: "intent" }'
                                   :hidden="!jsonSource"></tree-view>
                    </div>
                </div>
            </div>
        </form>

    </div> <!-- container -->
</template>

<script>
 import TranscribeService from '@/services/TranscribeService'
 import PronounceService from '@/services/PronounceService'

 export default {
     name: 'TranscribeSpeech',
     data: function() {
         return {
             jsonSource: null,
             sentence: '',

             holdRecording: false,
             tapRecording: false,
             interpreting: false,

             microphone: 'rhasspy',
             audioContext: null,
             recorder: null,

             sendHass: true
         }
     },

     methods: {
         transcribe: function() {
             this.sentence = ''

             var reader = new FileReader()
             var that = this
             reader.onload = function() {
                 that.$parent.beginAsync()
                 TranscribeService.transcribeWav(this.result, that.sendHass)
                     .then(request => {
                         that.$parent.alert('Got intent: ' + request.data.intent.name + ' in ' + request.data.time_sec.toFixed(2) + ' second(s)', 'success')
                         that.sentence = request.data.text
                         that.jsonSource = request.data
                     })
                     .then(() => that.$parent.endAsync())
                     .catch(err => that.$parent.error(err))
             }

             var files = this.$refs.wavFile.files;
             if (files.length > 0) {
                 reader.readAsArrayBuffer(files[0])
             } else {
                 this.$parent.alert('No WAV file', 'danger')
             }
         },

         getIntent: function() {
             this.$parent.beginAsync()
             TranscribeService.getIntent(this.sentence, this.sendHass)
                 .then(request => {
                     if (request.data.error) {
                         this.$parent.alert(request.data.error, 'danger')
                     } else {
                         this.$parent.alert('Got intent: ' + request.data.intent.name + ' in ' + request.data.time_sec.toFixed(2) + ' second(s)', 'success')
                     }

                     this.jsonSource = request.data
                 })
                 .then(() => this.$parent.endAsync())
                 .catch(err => this.$parent.error(err))
         },

         startRecording: function() {
             this.holdRecording = true
             if (this.microphone == 'browser') {
                 // Use browser microphone
                 this.getMicrophonePermission()
                 this.recorder.clear()
                 this.recorder.record()
             } else {
                 // Use Rhasspy microphone
                 TranscribeService.startRecording()
                                  .catch(err => this.$parent.error(err))
             }
         },

         stopRecording: function() {
             if (this.microphone == 'browser') {
                 // Use browser microphone
                 this.recorder.stop()

                 // Export recording data
                 var that = this
                 this.recorder.exportWAV(function(blob) {
                     that.interpreting = true
                     that.$parent.beginAsync()
                     TranscribeService.transcribeWav(blob, that.sendHass)
                         .then(request => {
                             that.holdRecording = false
                             that.tapRecording = false
                             that.jsonSource = request.data
                             that.sentence = request.data.text
                         })
                         .catch(err => that.$parent.error(err))
                         .then(() => {
                             that.holdRecording = false
                             that.tapRecording = false
                             that.interpreting = false
                             that.$parent.endAsync()
                         })
                 })
             } else {
                 // Use Rhasspy microphone
                 this.interpreting = true
                 this.$parent.beginAsync()
                 TranscribeService.stopRecording(this.sendHass)
                     .then(request => {
                         this.holdRecording = false
                         this.tapRecording = false
                         this.jsonSource = request.data
                         this.sentence = request.data.text
                     })
                     .catch(err => this.$parent.error(err))
                     .then(() => {
                         this.holdRecording = false
                         this.tapRecording = false
                         this.interpreting = false
                         this.$parent.endAsync()
                     })
             }
         },

         toggleRecording: function() {
             if (this.tapRecording) {
                 this.stopRecording();
             } else {
                 this.tapRecording = true
                 this.startRecording()
             }
         },

         getMicrophonePermission: function() {
             // Request microphone permissions
             if (this.audioContext == null) {
                 this.audioContext = new AudioContext()
             }

             if (this.recorder == null) {
                 var that = this
                 navigator.mediaDevices.getUserMedia({audio: true})
                          .then(function(stream) {
                              var input = that.audioContext.createMediaStreamSource(stream)
                              that.recorder = new Recorder(input)
                          })
             }
         },

         saySentence: function(event) {
             event.preventDefault()
             PronounceService.saySentence(this.sentence)
                  .catch(err => this.$parent.error(err))
         }
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
