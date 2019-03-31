<template>
    <div class="card mt-3">
        <div class="card-header">Overview</div>
        <div class="card-body">
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-rhasspy">MQTT</a>
                    </div>
                    <div class="col" v-bind:class="{ 'text-success': mqtt, 'text-danger': !mqtt }">
                        <p>{{ mqtt ? "enabled" : "DISABLED" }}</p>
                    </div>
                </div>
            </div>
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-handle">Intent Handling</a>
                    </div>
                    <div class="col" v-bind:class="{ 'text-success': handle, 'text-danger': !handle }">
                        <p>{{ handle ? profile.handle.system : "DISABLED" }}</p>
                    </div>
                </div>
            </div>
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-wake">Wake Word</a>
                    </div>
                    <div class="col" v-bind:class="{ 'text-success': wake, 'text-danger': !wake }">
                        <p>{{ wake ? profile.wake.system : "DISABLED" }}</p>
                    </div>
                </div>
            </div>
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-command">Voice Detection</a>
                    </div>
                    <div class="col" v-bind:class="{ 'text-success': command, 'text-danger': !command }">
                        <p>{{ command ? profile.command.system : "DISABLED" }}</p>
                    </div>
                </div>
            </div>
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-stt">Speech to Text</a>
                    </div>
                    <div class="col" v-bind:class="{ 'text-success': stt, 'text-danger': !stt }">
                        <p>{{ stt ? profile.speech_to_text.system : "DISABLED" }}</p>
                    </div>
                </div>
            </div>
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-intent">Intent Recognition</a>
                    </div>
                    <div class="col" v-bind:class="{ 'text-success': intent, 'text-danger': !intent }">
                        <p>{{ intent ? profile.intent.system : "DISABLED" }}</p>
                    </div>
                </div>
            </div>
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-tts">Text to Speech</a>
                    </div>
                    <div class="col" v-bind:class="{ 'text-success': stt, 'text-danger': !tts }">
                        <p>{{ tts ? profile.text_to_speech.system : "DISABLED" }}</p>
                    </div>
                </div>
            </div>
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-microphone">Microphone</a>
                    </div>
                    <div class="col" v-bind:class="{ 'text-success': microphone, 'text-danger': !microphone }">
                        <p>{{ microphone ? profile.microphone.system : "DISABLED" }}</p>
                    </div>
                </div>
            </div>
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-sounds">Sounds</a>
                    </div>
                    <div class="col" v-bind:class="{ 'text-success': sounds, 'text-danger': !sounds }">
                        <p>{{ sounds ? profile.sounds.system : "DISABLED" }}</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
 export default {
     name: 'Overview',
     props: {
         profile : Object
     },

     computed: {
         mqtt: function() {
             return this.profile.mqtt.enabled
         },

         microphone: function() {
             return this.profile.microphone.system != 'dummy'
         },

         sounds: function() {
             return this.profile.sounds.system != 'dummy'
         },

         handle: function() {
             return this.profile.handle.system != 'dummy'
         },

         wake: function() {
             return this.profile.wake.system != 'dummy'
         },

         command: function() {
             return this.profile.command.system != 'dummy'
         },

         stt: function() {
             return this.profile.speech_to_text.system != 'dummy'
         },

         intent: function() {
             return this.profile.intent.system != 'dummy'
         },

         tts: function() {
             return this.profile.text_to_speech.system != 'dummy'
         }
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
