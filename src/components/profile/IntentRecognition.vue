<template>
    <div class="card mt-3">
        <div class="card-header"><i class="fas fa-comment"></i>Intent Recognition</div>
        <div class="card-body">
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="intent-system" id="intent-system-dummy" value="dummy" v-model="profile.intent.system">
                        <label class="form-check-label" v-bind:class="{ 'text-danger': profile.intent.system == 'dummy' }" for="intent-system-dummy">
                            No intent recognition on this device
                        </label>
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="intent-system" id="intent-system-fuzzywuzzy" value="fuzzywuzzy" v-model="profile.intent.system">
                        <label class="form-check-label" for="intent-system-fuzzywuzzy">
                            Do intent recognition with <a href="https://github.com/seatgeek/fuzzywuzzy">fuzzywuzzy</a> on this device
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="fuzzywuzzy-min-confidence" class="col-form-label">Minimum Confidence</label>
                    <div class="col">
                        <input id="fuzzywuzzy-min-confidence" type="number" step="0.1" min="0" max="1" class="form-control" v-model.number="profile.intent.fuzzywuzzy.min_confidence" :disabled="profile.intent.system != 'fuzzywuzzy'">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="intent-system" id="intent-system-adapt" value="adapt" v-model="profile.intent.system">
                        <label class="form-check-label" for="intent-system-adapt">
                            Do intent recognition with <a href="https://github.com/MycroftAI/adapt/">Mycroft Adapt</a> on this device
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <p class="text-muted">Expecting words to ignore in <tt>{{ this.profile.intent.adapt.stop_words }}</tt></p>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="intent-system" id="intent-system-rasa" value="rasa" v-model="profile.intent.system">
                        <label class="form-check-label" for="intent-system-rasa">
                            Use remote <a href="https://rasa.com/docs/nlu/">RasaNLU</a> server
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="rasa-intent-url" class="col-form-label">RasaNLU URL</label>
                    <div class="col">
                        <input id="rasa-intent-url" type="text" class="form-control" v-model="profile.intent.rasa.url" :disabled="profile.intent.system != 'rasa'">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <div class="col text-muted">
                        Example: http://localhost:5000/
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="intent-system" id="intent-system-remote" value="remote" v-model="profile.intent.system">
                        <label class="form-check-label" for="intent-system-remote">
                            Use remote Rhasspy server
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="remote-intent-url" class="col-form-label">Rhasspy Text-to-Intent URL</label>
                    <div class="col">
                        <input id="remote-intent-url" type="text" class="form-control" v-model="profile.intent.remote.url" :disabled="profile.intent.system != 'remote'">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <div class="col text-muted">
                        Example: http://localhost:12101/api/text-to-intent
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
 export default {
     name: 'IntentRecognition',
     props: {
         profile : Object
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
