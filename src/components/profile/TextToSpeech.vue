<template>
    <div class="card mt-3">
        <div class="card-header"><i class="fas fa-paper-plane"></i>Text to Speech</div>
        <div class="card-body">
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="tts-system" id="tts-system-dummy" value="dummy" v-model="profile.text_to_speech.system">
                        <label class="form-check-label" v-bind:class="{ 'text-danger': profile.text_to_speech.system == 'dummy' }" for="tts-system-dummy">
                            No text to speech on this device
                        </label>
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <input type="checkbox" id="tts-disable-wake" v-model="profile.text_to_speech.disable_wake" :disabled="profile.text_to_speech.system == 'dummy'">

                    <label for="tts-disable-wake" class="col-form-label">Disable wake word while speaking</label>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="tts-system" id="tts-system-espeak" value="espeak" v-model="profile.text_to_speech.system">
                        <label class="form-check-label" for="tts-system-espeak">
                            Use <a href="http://espeak.sourceforge.net">eSpeak</a> on this device
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="marytts-voice" class="col-form-label">eSpeak Voice</label>
                    <div class="col">
                        <input id="espeak-voice" type="text" class="form-control" v-model="profile.text_to_speech.espeak.voice" :disabled="profile.text_to_speech.system != 'espeak'" placeholder="default">
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="tts-system" id="tts-system-flite" value="flite" v-model="profile.text_to_speech.system">
                        <label class="form-check-label" for="tts-system-flite">
                            Use <a href="http://www.festvox.org/flite">flite</a> on this device
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="flite-voice" class="col-form-label">flite Voice</label>
                    <div class="col">
                        <input id="flite-voice" type="text" class="form-control" v-model="profile.text_to_speech.flite.voice" :disabled="profile.text_to_speech.system != 'flite'" placeholder="kal16">
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="tts-system" id="tts-system-picotts" value="picotts" v-model="profile.text_to_speech.system">
                        <label class="form-check-label" for="tts-system-picotts">
                            Use pico-tts on this device
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="picotts-language" class="col-form-label">pico-tts Language</label>
                    <div class="col">
                        <input id="picotts-language" type="text" class="form-control" v-model="profile.text_to_speech.picotts.language" :disabled="profile.text_to_speech.system != 'picotts'" placeholder="default">
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="tts-system" id="tts-system-marytts" value="marytts" v-model="profile.text_to_speech.system">
                        <label class="form-check-label" for="tts-system-marytts">
                            Use marytts <a href="http://mary.dfki.de">MaryTTS</a> server
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="marytts-url" class="col-form-label">MaryTTS Server URL</label>
                    <div class="col">
                        <input id="marytts-url" type="text" class="form-control" v-model="profile.text_to_speech.marytts.url" :disabled="profile.text_to_speech.system != 'marytts'">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <div class="col text-muted">
                        Example: http://localhost:59125
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="marytts-voice" class="col-form-label">MaryTTS Voice</label>
                    <div class="col">
                        <input id="marytts-voice" type="text" class="form-control" v-model="profile.text_to_speech.marytts.voice" :disabled="profile.text_to_speech.system != 'marytts'" placeholder="default">
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="tts-system" id="tts-system-wavenet" value="wavenet" v-model="profile.text_to_speech.system">
                        <label class="form-check-label" for="tts-system-wavenet">
                            Use Google Wavenet
                        </label>
                    </div>
                </div>
                <div class="alert alert-warning" v-if="profile.text_to_speech.system == 'wavenet'">
                    Requires an internet connection and <a href="https://cloud.google.com/text-to-speech">an account</a>.
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="wavenet-wavenet_voice" class="col-form-label">Google Wavenet Voice</label>
                    <div class="col">
                        <input id="wavenet-wavenet_voice" type="text" class="form-control" v-model="profile.text_to_speech.wavenet.voice" :disabled="profile.text_to_speech.system != 'wavenet'" placeholder="Wavenet-C">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <div class="col-auto">
                    <label for="wavenet-gender" class="col-form-label col">Gender</label>
                    </div>
                    <div class="col-auto">
                        <select id="wavenet-gender" :disabled="profile.text_to_speech.system != 'wavenet'" v-model="profile.text_to_speech.wavenet.gender">
                        <option v-bind:key="item" v-for="item in genders" :value="item">{{item}}</option>
                        </select>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="wavenet-language_code" class="col-form-label">Language code (xx-XX)</label>
                    <div class="col">
                        <input id="wavenet-language_code" type="text" class="form-control" v-model="profile.text_to_speech.wavenet.language_code" :disabled="profile.text_to_speech.system != 'wavenet'">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <div class="col-auto">
                    <label for="wavenet-samplerate" class="col-form-label col">Sample Rate</label>
                    </div>
                    <div class="col-auto">
                        <select id="wavenet-samplerate" :disabled="profile.text_to_speech.system != 'wavenet'" v-model="profile.text_to_speech.wavenet.sample_rate">
                         <option v-bind:key="item" v-for="item in sample_rates" :value="item">{{item}}</option>
                        </select>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <div class="col text-muted">
                        Expecting JSON credentials at: <tt>{{ profile.text_to_speech.wavenet.credentials_json }}</tt>
                        <br>
                        WAV files will be cached in: <tt>{{ profile.text_to_speech.wavenet.cache_dir }}</tt>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
 export default {
     name: 'TextToSpeech',
     props: {
         profile : Object
     },
     data: function () {
         return {
             genders: ['FEMALE','MALE','NEUTRAL'],
             sample_rates: [8000, 11025, 16000, 22050, 44100]
         }
     },
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
