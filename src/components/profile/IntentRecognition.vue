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
                    <input type="checkbox" id="intent-error-sound" v-model="profile.intent.error_sound" :disabled="profile.intent.system == 'dummy'">

                    <label for="intent-error-sound" class="col-form-label">Play <tt>error</tt> sound when intent not recognized</label>
                </div>
                <div class="form-row">
                    <p class="text-muted">
                        See <a href="#profile-sounds">Sounds section</a> below.
                    </p>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="intent-system" id="intent-system-fsticuffs" value="fsticuffs" v-model="profile.intent.system">
                        <label class="form-check-label" for="intent-system-fsticuffs">
                            Do intent recognition with <a href="https://www.openfst.org">OpenFST</a> on this device
                        </label>
                    </div>
                </div>

            </div>
            <div class="form-group">
                <div class="form-row">
                    <input type="checkbox" id="fsticuffs-fuzzy" v-model="profile.intent.fsticuffs.fuzzy" :disabled="profile.intent.system != 'fsticuffs'">

                    <label for="fsticuffs-fuzzy" class="col-form-label">Fuzzy text matching</label>
                </div>
                <div class="form-row" v-if="profile.intent.fsticuffs.fuzzy">
                    <p class="text-muted">Expecting words to ignore in <tt>{{ this.profile.intent.adapt.stop_words }}</tt></p>
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
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="intent-system" id="intent-system-adapt" value="adapt" v-model="profile.intent.system">
                        <label class="form-check-label" for="intent-system-adapt">
                            Do intent recognition with <a href="https://github.com/MycroftAI/adapt/">Mycroft Adapt</a> on this device
                        </label>
                    </div>
                </div>
                <div class="form-row">
                    <p class="text-muted">Expecting words to ignore in <tt>{{ this.profile.intent.adapt.stop_words }}</tt></p>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="intent-system" id="intent-system-conversation" value="conversation" v-model="profile.intent.system">
                        <label class="form-check-label" for="intent-system-conversation">
                            Send transcriptions to <a href="https://www.home-assistant.io/integrations/conversation/">Home Assistant's conversation API</a>
                        </label>
                    </div>
                </div>
                <div class="form-row">
                    <input type="checkbox" id="conversation-handle-speech" v-model="profile.intent.conversation.handle_speech" :disabled="profile.intent.system != 'conversation'">
                    <label for="conversation-handle-speech" class="col-form-label">Speak response with Rhasspy</label>
                </div>
            </div>
            <hr>
            <!-- <div class="form-group"> -->
            <!-- <div class="form-row"> -->
            <!-- <div class="form-check"> -->
            <!-- <input class="form-check-input" type="radio" name="intent-system" id="intent-system-flair" value="flair" v-model="profile.intent.system" :disabled="!profile.intent.flair.compatible"> -->
            <!-- <label class="form-check-label" for="intent-system-flair"> -->
            <!-- Do intent recognition with <a href="https://github.com/zalandoresearch/flair">flair</a> on this device -->
            <!-- </label> -->
            <!-- </div> -->
            <!-- </div> -->
            <!-- <div class="alert alert-warning" v-if="!profile.intent.flair.compatible"> -->
            <!-- Not compatible with this profile -->
            <!-- </div> -->
            <!-- </div> -->
            <!-- <div class="form-group"> -->
            <!-- <div class="form-row"> -->
            <!-- <input type="checkbox" id="flair-do-sampling" v-model="profile.intent.flair.do_sampling" :disabled="profile.intent.system != 'flair'"> -->
            <!-- <label for="flair-do-sampling" class="col-form-label">Generate Random Sample Sentences</label> -->
            <!-- </div> -->
            <!-- <div class="alert alert-warning" v-if="!profile.intent.flair.do_sampling"> -->
            <!-- All possible sentences will be used as training data (may take a long time to train) -->
            <!-- </div> -->
            <!-- </div> -->
            <!-- <div class="form-group"> -->
            <!-- <div class="form-row"> -->
            <!-- <label for="flair-samples" class="col-form-label">Samples Per Intent</label> -->
            <!-- <div class="col"> -->
            <!-- <input id="flair-samples" type="number" class="form-control" min="1" v-model.number="profile.intent.flair.num_samples" :disabled="profile.intent.system != 'flair' || !profile.intent.flair.do_sampling"> -->
            <!-- </div> -->
            <!-- </div> -->
            <!-- </div> -->
            <!-- <div class="form-group"> -->
            <!-- <div class="form-row"> -->
            <!-- <label for="flair-max-epochs" class="col-form-label">Maximum Training Epochs</label> -->
            <!-- <div class="col"> -->
            <!-- <input id="flair-max-epochs" type="number" class="form-control" min="1" v-model.number="profile.intent.flair.max_epochs" :disabled="profile.intent.system != 'flair'"> -->
            <!-- </div> -->
            <!-- </div> -->
            <!-- </div> -->
            <!-- <div class="form-group"> -->
            <!-- <div class="form-row"> -->
            <!-- <p class="text-muted">Models will be stored in <tt>{{ this.profile.intent.flair.data_dir }}</tt></p> -->
            <!-- </div> -->
            <!-- </div> -->
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="intent-system" id="intent-system-rasa" value="rasa" v-model="profile.intent.system">
                        <label class="form-check-label" for="intent-system-rasa">
                            Use remote <a href="https://rasa.com/docs/nlu/">Rasa NLU</a> server
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="rasa-intent-url" class="col-form-label">Rasa NLU URL</label>
                    <div class="col">
                        <input id="rasa-intent-url" type="text" class="form-control" v-model="profile.intent.rasa.url" :disabled="profile.intent.system != 'rasa'">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <div class="col text-muted">
                        Example: http://localhost:5005/
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
