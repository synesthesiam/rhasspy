<template>
    <div class="card mt-3">
        <div class="card-header"><i class="fas fa-microphone-alt-slash"></i>Voice Detection</div>
        <div class="card-body">
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="command-system" id="command-system-dummy" value="dummy" v-model="profile.command.system">
                        <label class="form-check-label" v-bind:class="{ 'text-danger': profile.command.system == 'dummy' }" for="command-system-dummy">
                            No voice commands on this device
                        </label>
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="command-system" id="command-system-webrtcvad" value="webrtcvad" v-model="profile.command.system">
                        <label class="form-check-label" for="command-system-webrtcvad">
                            Use <a href="https://github.com/wiseman/py-webrtcvad">webrtcvad</a> and listen for silence
                        </label>
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="command-system" id="command-system-hermes" value="hermes" v-model="profile.command.system">
                        <label class="form-check-label" for="command-system-hermes">
                            Use MQTT (<a href="https://docs.snips.ai/reference/hermes">Hermes protocol</a>)
                        </label>
                    </div>
                </div>
                <div class="form-row">
                    <div class="col text-muted">
                        Rhasspy will listen for:
                        <ul>
                            <li><tt>hermes/asr/startListening</tt></li>
                            <li><tt>hermes/asr/stopListening</tt></li>
                        </ul>
                        <div class="alert alert-danger" v-if="profile.command.system == 'hermes' && !profile.mqtt.enabled">
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
     name: 'VoiceDetection',
     props: {
         profile : Object
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
