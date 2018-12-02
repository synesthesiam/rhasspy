<template>
    <div class="container">
        <form class="form" v-on:submit.prevent="getIntent">
            <div class="form-group">
                <div class="form-row">
                    <div class="col-auto">
                        <label for="device" class="col-form-label col">Audio Device</label>
                    </div>
                    <div class="col-auto">
                        <select id="device" v-model="device">
                            <option value="-1">Default Device</option>
                            <option v-for="(desc, id) in microphones" :value="id" v-bind:key="id">{{ id }}: {{ desc }}</option>
                        </select>
                    </div>
                    <div class="col-auto">
                        <button type="button" class="btn"
                                v-bind:class="{ 'btn-danger': recording, 'btn-primary': !recording }"
                                @mousedown="startRecording" @mouseup="stopRecording"
                                :disabled="interpreting">{{ recording ? 'Release to Stop' : 'Hold to Record' }}</button>
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
                        <button type="button" class="btn btn-info" @click="transcribe">Transcribe WAV</button>
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
                        <button type="submit" class="btn btn-secondary">Get Intent</button>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row mt-5">
                    <div class="col-auto">
                        <input type="checkbox" id="sendHass" v-model="sendHass">
                        <label class="ml-1" for="sendHass">Send to Home Assistant</label>
                    </div>
                </div>
            </div>
            <hr />
            <div class="form-group">
                <div class="form-row mt-5">
                    <div>
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

 export default {
     name: 'TranscribeSpeech',
     props: { profile : String },
     data: function() {
         return {
             jsonSource: null,
             sentence: '',

             recording: false,
             interpreting: false,
             device: '-1',

             microphones: {},

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
                 TranscribeService.transcribeWav(that.profile, this.result, that.sendHass)
                     .then(request => {
                         that.$parent.alert('Got intent: ' + request.data.intent.name + ' in ' + request.data.time_sec.toFixed(2) + ' second(s)', 'success')
                         that.sentence = request.data.text
                         that.jsonSource = request.data
                     })
                     .catch(err => that.$parent.alert(err.response.data, 'danger'))
                     .then(() => that.$parent.endAsync())
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
             TranscribeService.getIntent(this.profile, this.sentence, this.sendHass)
                 .then(request => {
                     this.$parent.alert('Got intent: ' + request.data.intent.name, 'success')
                     this.jsonSource = request.data
                 })
                 .catch(err => this.$parent.alert(err.response.data, 'danger'))
                 .then(() => this.$parent.endAsync())
         },

         startRecording: function() {
             TranscribeService.startRecording(this.profile, this.device)
                              .then(() => {
                                  this.recording = true
                              })
                              .catch(err => this.$parent.alert(err.response.data, 'danger'))
         },

         stopRecording: function() {
             this.interpreting = true
             this.$parent.beginAsync()
             TranscribeService.stopRecording(this.profile, this.sendHass)
                 .then(request => {
                     this.recording = false
                     this.jsonSource = request.data
                     this.sentence = request.data.text
                 })
                 .catch(err => this.$parent.alert(err.response.data, 'danger'))
                 .then(() => {
                     this.interpreting = false
                     this.$parent.endAsync()
                 })
         }
     },

     mounted: function() {
         TranscribeService.getMicrophones(this.profile)
                          .then(request => {
                              this.microphones = request.data
                          })
                          .catch(err => this.$parent.alert(err.response.data, 'danger'))
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
