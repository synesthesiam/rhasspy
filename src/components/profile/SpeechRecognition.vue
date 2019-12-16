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
                        <input class="form-check-input" type="radio" name="stt-system" id="stt-system-pocketsphinx" value="pocketsphinx" v-model="profile.speech_to_text.system" :disabled="!profile.speech_to_text.pocketsphinx.compatible">
                        <label class="form-check-label" for="stt-system-pocketsphinx">
                            Do speech recognition with <a href="https://github.com/cmusphinx/pocketsphinx">pocketsphinx</a> on this device
                        </label>
                    </div>
                </div>
                <div class="alert alert-warning" v-if="!profile.speech_to_text.pocketsphinx.compatible">
                    Not compatible with this profile
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <input type="checkbox" id="pocketsphinx-open" v-model="profile.speech_to_text.pocketsphinx.open_transcription">
                    <label for="pocketsphinx-open" class="col-form-label">Open transcription mode (no custom voice commands)</label>
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
                        <input class="form-check-input" type="radio" name="stt-system" id="stt-system-kaldi" value="kaldi" v-model="profile.speech_to_text.system" :disabled="!profile.speech_to_text.kaldi.compatible">
                        <label class="form-check-label" for="stt-system-kaldi">
                            Do speech recognition with <a href="http://kaldi-asr.org">kaldi</a> on this device
                        </label>
                    </div>
                </div>
                <div class="alert alert-warning" v-if="!profile.speech_to_text.kaldi.compatible">
                    Not compatible with this profile
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <input type="checkbox" id="kaldi-open" v-model="profile.speech_to_text.kaldi.open_transcription">
                    <label for="kaldi-open" class="col-form-label">Open transcription mode (no custom voice commands)</label>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="kaldi-kaldi-dir" class="col-form-label">Kaldi Directory</label>
                    <div class="col">
                        <input id="kaldi-kaldi-dir" type="text" class="form-control" v-model="profile.speech_to_text.kaldi.kaldi_dir" :disabled="profile.speech_to_text.system != 'kaldi'">
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
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="stt-system" id="stt-system-hass_stt" value="hass_stt" v-model="profile.speech_to_text.system">
                        <label class="form-check-label" for="stt-system-hass_stt">
                            Use a Home Assistant <a href="https://www.home-assistant.io/integrations/stt">STT Platform</a>
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="stt-hass-platform" class="col-form-label">STT Platform Name</label>
                    <div class="col">
                        <input id="stt-hass-platform" type="text" class="form-control" v-model="profile.speech_to_text.hass_stt.platform" :disabled="profile.speech_to_text.system != 'hass_stt'">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <div class="col text-muted">
                        Rhasspy will stream audio to: {{ profile.home_assistant.url }}api/stt/{{ profile.speech_to_text.hass_stt.platform }}
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="stt-hass-rate" class="col-form-label">Sample Rate</label>
                    <div class="col">
                        <input id="stt-hass-rate" type="text" class="form-control" v-model="profile.speech_to_text.hass_stt.sample_rate" :disabled="profile.speech_to_text.system != 'hass_stt'">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="stt-hass-bitsize" class="col-form-label">Bit Size</label>
                    <div class="col">
                        <input id="stt-hass-bitsize" type="text" class="form-control" v-model="profile.speech_to_text.hass_stt.bit_size" :disabled="profile.speech_to_text.system != 'hass_stt'">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="stt-hass-channels" class="col-form-label">Channels</label>
                    <div class="col">
                        <input id="stt-hass-channels" type="text" class="form-control" v-model="profile.speech_to_text.hass_stt.channels" :disabled="profile.speech_to_text.system != 'hass_stt'">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="stt-hass-language" class="col-form-label">Language</label>
                    <div class="col">
                        <input id="stt-hass-language" type="text" class="form-control" v-model="profile.speech_to_text.hass_stt.language" :disabled="profile.speech_to_text.system != 'hass_stt'">
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
