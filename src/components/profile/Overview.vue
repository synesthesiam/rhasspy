<template>
    <div class="card mt-3">
        <div class="card-header">Overview</div>
        <div class="card-body">
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-rhasspy">MQTT</a>
                    </div>
                    <div class="col badge p-2 mb-2" v-bind:class="{ 'badge-success': mqtt, 'badge-danger': !mqtt }">
                        {{ mqtt ? "enabled" : "DISABLED" }}
                    </div>
                </div>
            </div>
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-handle">Intent Handling</a>
                    </div>
                    <div class="col badge p-2 mb-2" v-bind:class="{ 'badge-success': handle, 'badge-danger': !handle }">
                        {{ handle ? profile.handle.system : "DISABLED" }}
                    </div>
                </div>
            </div>
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-wake">Wake Word</a>
                    </div>
                    <div class="col badge p-2 mb-2" v-bind:class="{ 'badge-success': wake, 'badge-danger': !wake }">
                        {{ wake ? profile.wake.system : "DISABLED" }}
                    </div>
                </div>
            </div>
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-command">Voice Detection</a>
                    </div>
                    <div class="col badge p-2 mb-2" v-bind:class="{ 'badge-success': command, 'badge-danger': !command }">
                        {{ command ? profile.command.system : "DISABLED" }}
                    </div>
                </div>
            </div>
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-stt">Speech to Text</a>
                    </div>
                    <div class="col badge p-2 mb-2" v-bind:class="{ 'badge-success': stt, 'badge-danger': !stt }">
                        {{ stt ? profile.speech_to_text.system : "DISABLED" }}
                    </div>
                </div>
            </div>
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-intent">Intent Recognition</a>
                    </div>
                    <div class="col badge p-2 mb-2" v-bind:class="{ 'badge-success': intent, 'badge-danger': !intent }">
                        {{ intent ? profile.intent.system : "DISABLED" }}
                    </div>
                </div>
            </div>
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-tts">Text to Speech</a>
                    </div>
                    <div class="col badge p-2 mb-2" v-bind:class="{ 'badge-success': stt, 'badge-danger': !tts }">
                        {{ tts ? profile.text_to_speech.system : "DISABLED" }}
                    </div>
                </div>
            </div>
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-microphone">Microphone</a>
                    </div>
                    <div class="col badge p-2 mb-2" v-bind:class="{ 'badge-success': microphone, 'badge-danger': !microphone }">
                        {{ microphone ? profile.microphone.system : "DISABLED" }}
                    </div>
                </div>
            </div>
            <div class="form-group m-0 p-0">
                <div class="form-row">
                    <div class="col">
                        <a href="#profile-sounds">Sounds</a>
                    </div>
                    <div class="col badge p-2 mb-2" v-bind:class="{ 'badge-success': sounds, 'badge-danger': !sounds }">
                        {{ sounds ? profile.sounds.system : "DISABLED" }}
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
