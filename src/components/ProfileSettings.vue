<template>
    <div class="container">
        <form class="form" v-on:submit.prevent="saveSettings">
            <div class="form-group row">
                <label for="language" class="col-xs col-form-label ml-3">Language</label>
                <div class="col-sm-auto">
                    <input id="language" type="text" class="form-control" v-model="this.profileSettings.language">
                </div>
            </div>

            <hr />

            <div class="form-row">
                <h3>Wake</h3>
            </div>
            <div class="form-group row mt-2">
                <label for="wake-system" class="col-sm-2 col-form-label">System</label>
                <div class="col-sm-10">
                    <select id="wake-system">
                        <option>pocketsphinx</option>
                    </select>
                </div>
            </div>
            <div class="form-group row mt-2">
                <label for="wake-keyphrase" class="col-sm-2 col-form-label">Keyphrase</label>
                <div class="col-sm-10">
                    <input id="wake-keyphrase" type="text" class="form-control" v-model="this.profileSettings.wake.pocketsphinx.keyphrase">
                </div>
            </div>
            <div class="form-group row mt-2">
                <label for="wake-threshold" class="col-sm-2 col-form-label">Threshold</label>
                <div class="col-sm-10">
                    <input id="wake-threshold" type="text" class="form-control" v-model="this.profileSettings.wake.pocketsphinx.threshold">
                </div>
            </div>

            <hr />

            <div class="form-row">
                <h3>Speech to Text</h3>
            </div>
            <div class="form-group row mt-2">
                <label for="stt-system" class="col-sm-2 col-form-label">System</label>
                <div class="col-sm-10">
                    <select id="stt-system">
                        <option>pocketsphinx</option>
                    </select>
                </div>
            </div>

            <hr />

            <div class="form-row">
                <h3>Intent</h3>
            </div>
            <div class="form-group row mt-2">
                <label for="intent-system" class="col-sm-2 col-form-label">System</label>
                <div class="col-sm-10">
                    <select id="intent-system">
                        <option>fuzzywuzzy</option>
                    </select>
                </div>
            </div>

            <hr />

            <div class="form-row">
                <h3>Home Assistant</h3>
            </div>
            <div class="form-group row mt-3">
                <label for="hass-url" class="col-sm-2 col-form-label">URL</label>
                <div class="col-sm-10">
                    <input id="hass-url" type="text" class="form-control" v-model="this.profileSettings.home_assistant.url">
                </div>
            </div>
            <div class="form-group row">
                <label for="hass-format" class="col-sm-2 col-form-label">Event Type Format</label>
                <div class="col-sm-10">
                    <input id="hass-format" type="text" class="form-control" v-model="this.profileSettings.home_assistant.event_type_format">
                </div>
            </div>
            <div class="form-group row">
                <label for="hass-password" class="col-sm-2 col-form-label">API Password</label>
                <div class="col-sm-10">
                    <input id="hass-password" type="text" class="form-control" v-model="this.profileSettings.home_assistant.api_password">
                </div>
            </div>

            <hr />

            <div class="form-row">
                <h3>Text to Speech</h3>
            </div>
            <div class="form-group row mt-2">
                <label for="tts-system" class="col-sm-2 col-form-label">System</label>
                <div class="col-sm-10">
                    <select id="tts-system">
                        <option>espeak</option>
                    </select>
                </div>
            </div>

            <hr />

            <div class="form-row">
                <h3>Training</h3>
            </div>
            <div class="form-group row mt-2">
                <label for="tokenizer" class="col-sm-2 col-form-label">Tokenizer</label>
                <div class="col-sm-10">
                    <select id="tokenizer">
                        <option>regex</option>
                    </select>
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
         profile : String
     },
     data: function () {
         return {
             profileSettings: {}
         }
     },

     methods: {
         refreshSettings: function() {
             ProfileService.getProfileSettings(this.profile)
                           .then(request => {
                               this.profileSettings = request.data
                           })
                           .catch(err => this.$parent.alert(err.response.data, 'danger'))
         },

         saveSettings: function() {
         }
     },

     mounted: function() {
         this.refreshSettings()
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
