<template>
    <div class="card mt-3">
        <div class="card-header"><i class="fas fa-phone-volume"></i>Speech Recognition</div>
        <div class="card-body">
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="stt-system" id="stt-system-dummy" value="dummy" v-model="profile.speech_to_text.system">
                        <label class="form-check-label" v-bind:class="{ 'text-danger': profile.speech_to_text.system == 'dummy' }" for="stt-system-dummy">
                            No speech recognition on this device
                        </label>
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="stt-system" id="stt-system-pocketsphinx" value="pocketsphinx" v-model="profile.speech_to_text.system">
                        <label class="form-check-label" for="stt-system-pocketsphinx">
                            Do speech recognition with <a href="https://github.com/cmusphinx/pocketsphinx">pocketsphinx</a> on this device
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="pocketsphinx-min-confidence" class="col-form-label">Minimum Confidence</label>
                    <div class="col">
                        <input id="pocketsphinx-min-confidence" type="number" step="0.01" min="0" max="1" class="form-control" v-model.number="profile.speech_to_text.pocketsphinx.min_confidence" :disabled="profile.speech_to_text.system != 'pocketsphinx'">
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="stt-system" id="stt-system-remote" value="remote" v-model="profile.speech_to_text.system">
                        <label class="form-check-label" for="stt-system-remote">
                            Use remote Rhasspy server for speech recognition
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="stt-url" class="col-form-label">Rhasspy Speech-to-Text URL</label>
                    <div class="col">
                        <input id="stt-url" type="text" class="form-control" v-model="profile.speech_to_text.remote.url" :disabled="profile.speech_to_text.system != 'remote'">
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
</template>

<script>
 export default {
     name: 'SpeechRecognition',
     props: {
         profile : Object
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
