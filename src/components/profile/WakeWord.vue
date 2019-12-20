<template>
    <div class="card mt-3">
        <div class="card-header"><i class="fas fa-exclamation-circle"></i>Wake Word</div>
        <div class="card-body">
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="wake-system" id="wake-system-dummy" value="dummy" v-model="profile.wake.system">
                        <label class="form-check-label" v-bind:class="{ 'text-danger': profile.wake.system == 'dummy' }" for="wake-system-dummy">
                            No wake word on this device
                        </label>
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="wake-system" id="wake-system-pocketsphinx" value="pocketsphinx" v-model="profile.wake.system" :disabled="!profile.wake.pocketsphinx.compatible">
                        <label class="form-check-label" for="wake-system-pocketsphinx">
                            Use <a href="https://github.com/cmusphinx/pocketsphinx">Pocketsphinx</a> on this device
                        </label>
                    </div>
                </div>
                <div class="alert alert-warning" v-if="!profile.wake.pocketsphinx.compatible">
                    Not compatible with this profile
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="wake-pocketsphinx-keyphrase" class="col-form-label">Wake Keyphrase</label>
                    <div class="col-sm-auto">
                        <input id="wake-pocketsphinx-keyphrase" type="text" class="form-control" v-model="profile.wake.pocketsphinx.keyphrase" :disabled="profile.wake.system != 'pocketsphinx'">
                    </div>
                    <div class="col text-muted">
                        3-4 syllables recommended
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="wake-pocketsphinx-sensitivity" class="col-form-label">Sensitivity</label>
                    <div class="col-sm-auto">
                        <input id="wake-pocketsphinx-sensitivity" type="number" min="0" max="1" step="0.1" class="form-control" v-model="psSensitivity" :disabled="profile.wake.system != 'pocketsphinx'">
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="wake-system" id="wake-system-snowboy" value="snowboy" v-model="profile.wake.system">
                        <label class="form-check-label" for="wake-system-snowboy">
                            Use <a href="https://snowboy.kitt.ai">snowboy</a> on this device
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="snowboy-model" class="col-form-label">Model Names</label>
                    <div class="col-sm-auto">
                        <input id="snowboy-model" type="text" class="form-control" v-model="profile.wake.snowboy.model" :disabled="profile.wake.system != 'snowboy'">
                    </div>
                </div>
                <div class="form-row">
                    <div class="col text-muted">
                        Put models in the <tt>snowboy</tt> directory in your profile
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="wake-snowboy-sensitivity" class="col-form-label">Sensitivity</label>
                    <div class="col-sm-auto">
                        <input id="wake-snowboy-sensitivity" type="text" class="form-control" v-model="profile.wake.snowboy.sensitivity" :disabled="profile.wake.system != 'snowboy'"> <span class="text-muted">(comma-separated)</span>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <input type="checkbox" id="wake-snowboy-applyfrontend" v-model="profile.wake.snowboy.apply_frontend" :disabled="profile.wake.system != 'snowboy'">
                    <label for="wake-snowboy-applyfrontend" class="col-form-label">Apply Frontend (<a href="https://github.com/kitt-ai/snowboy#pretrained-universal-models" title="Parameters for pre-trained models">more info</a>)</label>
                </div>
            </div>
            <div class="form-group">
                <p>
                    See <a href="https://rhasspy.readthedocs.io/en/latest/wake-word/#snowboy">documentation</a> for how to use multiple wake words.
                </p>
            </div>
            <hr>
            <!-- <div class="form-group"> -->
            <!-- <div class="form-row"> -->
            <!-- <div class="form-check"> -->
            <!-- <input class="form-check-input" type="radio" name="wake-system" id="wake-system-precise" value="precise" v-model="profile.wake.system"> -->
            <!-- <label class="form-check-label" for="wake-system-precise"> -->
            <!-- Use <a href="https://github.com/MycroftAI/mycroft-precise">Mycroft Precise</a> on this device -->
            <!-- </label> -->
            <!-- </div> -->
            <!-- </div> -->
            <!-- </div> -->
            <!-- <div class="form-group"> -->
            <!-- <div class="form-row"> -->
            <!-- <label for="precise-model" class="col-form-label">Model Name</label> -->
            <!-- <div class="col-sm-auto"> -->
            <!-- <input id="precise-model" type="text" class="form-control" v-model="profile.wake.precise.model" :disabled="profile.wake.system != 'precise'"> -->
            <!-- </div> -->
            <!-- <div class="col text-muted"> -->
            <!-- Put models in your profile directory -->
            <!-- </div> -->
            <!-- </div> -->
            <!-- </div> -->
            <!-- <hr> -->
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="wake-system" id="wake-system-porcupine" value="porcupine" v-model="profile.wake.system">
                        <label class="form-check-label" for="wake-system-porcupine">
                            Use <a href="https://github.com/Picovoice/Porcupine">Porcupine</a> on this device
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="porcupine-model" class="col-form-label">Keyword Files</label>
                    <div class="col-sm-auto">
                        <input id="porcupine-keyword" type="text" class="form-control" v-model="profile.wake.porcupine.keyword_path" :disabled="profile.wake.system != 'porcupine'">
                    </div>
                </div>
                <div class="form-row">
                    <div class="col text-muted">
                        Put keyword files in the <tt>porcupine</tt> directory in your profile
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="wake-porcupine-sensitivity" class="col-form-label">Sensitivity</label>
                    <div class="col-sm-auto">
                        <input id="wake-porcupine-sensitivity" type="text" class="form-control" v-model="profile.wake.porcupine.sensitivity" :disabled="profile.wake.system != 'porcupine'"> <span class="text-muted">(comma-separated)</span>
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="wake-system" id="wake-system-hermes" value="hermes" v-model="profile.wake.system">
                        <label class="form-check-label" for="wake-system-hermes">
                            Wake up on MQTT message (<a href="https://docs.snips.ai/reference/hermes">Hermes protocol</a>)
                        </label>
                    </div>
                </div>
                <div class="form-row">
                    <div class="col text-muted">
                        Rhasspy will listen for a message on: <tt>hermes/hotword/{{ this.profile.wake.hermes.wakeword_id }}/detected</tt>
                        <div class="alert alert-danger" v-if="profile.wake.system == 'hermes' && !profile.mqtt.enabled">
                            MQTT is not enabled
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
 export default {
     name: 'WakeWord',
     props: {
         profile : Object
     },
     computed: {
         psSensitivity: {
             get: function() {
                 var high = 50
                 var low = 5

                 var t = this.profile.wake.pocketsphinx.threshold
                 var exp = -Math.log10(t)
                 var s = (exp - low) / (high - low)
                 return Math.min(1, Math.max(0, s)).toFixed(1)
             },

             set: function(sensitivity) {
                 var high = 50
                 var low = 5

                 var exp = (sensitivity * (high - low)) + low
                 var t = Math.pow(10, -exp)
                 this.profile.wake.pocketsphinx.threshold = t
             }
         }
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
