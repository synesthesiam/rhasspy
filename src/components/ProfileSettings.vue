<template>
    <div class="container">
        <form class="form" v-on:submit.prevent="saveSettings">
            <div class="form-group">
                <div class="form-row text-muted pl-1">
                    <p>
                        This is a simplified interface to edit your <a href="https://rhasspy.readthedocs.io/en/latest/profiles/">your Rhasspy profile</a>. If you want to access the JSON directly, see the Advanced tab or <tt>profile.json</tt>.
                    </p>
                </div>
            </div>

            <h2>{{ this.profile.name || this.profile.language }}</h2>

            <Overview :profile="profile" />

            <button class="btn btn-primary mt-3">Save Settings</button>
            <Rhasspy id="profile-rhasspy"
                     :profile="profile"
                     :defaults="defaults"
                     :profiles="profiles"
                     v-on:begin-async="$emit('begin-async')"
                     v-on:end-async="$emit('end-async')"
                     v-on:restart="$emit('restart')"
            />

            <IntentHandling id="profile-handle" :profile="profile" />
            <button class="btn btn-primary mt-3">Save Settings</button>

            <WakeWord id="profile-wake" :profile="profile" />
            <button class="btn btn-primary mt-3">Save Settings</button>

            <VoiceDetection id="profile-command" :profile="profile" />
            <button class="btn btn-primary mt-3">Save Settings</button>

            <SpeechRecognition id="profile-stt" :profile="profile" />
            <button class="btn btn-primary mt-3">Save Settings</button>

            <IntentRecognition id="profile-intent" :profile="profile" />
            <button class="btn btn-primary mt-3">Save Settings</button>

            <TextToSpeech id="profile-tts" :profile="profile" />
            <button class="btn btn-primary mt-3">Save Settings</button>

            <AudioRecording id="profile-microphone"
                            :profile="profile"
                            v-on:begin-async="$emit('begin-async')"
                            v-on:end-async="$emit('end-async')"
                            v-on:alert="$emit('alert', $event)"
                            v-on:error="$emit('error', $event)" />
            <button class="btn btn-primary mt-3">Save Settings</button>

            <AudioPlaying id="profile-sounds" :profile="profile" />
            <button class="btn btn-primary mt-3">Save Settings</button>

        </form>
    </div> <!-- container -->
</template>

<script>
 import ProfileService from '@/services/ProfileService'

 import Overview from '@/components/profile/Overview'
 import Rhasspy from '@/components/profile/Rhasspy'
 import IntentHandling from '@/components/profile/IntentHandling'
 import WakeWord from '@/components/profile/WakeWord'
 import VoiceDetection from '@/components/profile/VoiceDetection'
 import SpeechRecognition from '@/components/profile/SpeechRecognition'
 import IntentRecognition from '@/components/profile/IntentRecognition'
 import AudioRecording from '@/components/profile/AudioRecording'
 import AudioPlaying from '@/components/profile/AudioPlaying'
 import TextToSpeech from '@/components/profile/TextToSpeech'

 export default {
     name: 'ProfileSettings',
     components: {
         Overview,
         IntentHandling,
         Rhasspy,
         WakeWord,
         VoiceDetection,
         SpeechRecognition,
         IntentRecognition,
         AudioRecording,
         AudioPlaying,
         TextToSpeech
     },

     props: {
         profile : Object,
         profiles: Array,
         defaults: Object
     },

     methods: {
         saveSettings: function() {
             // POST to server
             this.$parent.beginAsync()
             ProfileService.updateProfileSettings(this.profile)
                 .then(request => this.$parent.alert(request.data, 'success'))
                 .then(() => {
                     this.$parent.endAsync()
                     if (confirm("Settings saved. Restart Rhasspy?")) {
                         this.$parent.restart()
                     }
                 })
                 .catch(err => this.$parent.error(err))
         },
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
