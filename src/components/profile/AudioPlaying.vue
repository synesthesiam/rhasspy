<template>
    <div class="card mt-3">
        <div class="card-header"><i class="fas fa-volume-up"></i>Audio Playing</div>
        <div class="card-body">
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="sounds-system" id="sounds-system-dummy" value="dummy" v-model="profile.sounds.system">
                        <label class="form-check-label" v-bind:class="{ 'text-danger': profile.sounds.system == 'dummy' }" for="sounds-system-dummy">
                            No playback on this device
                        </label>
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="sounds-system" id="sounds-system-aplay" value="aplay" v-model="profile.sounds.system" @click="getSpeakers('aplay')">
                        <label class="form-check-label" for="sounds-system-aplay">
                            Use <tt>aplay</tt> directly (ALSA)
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <div class="col-auto">
                        <label for="device" class="col-form-label col">Output Device</label>
                    </div>
                    <div class="col-auto">
                        <select id="device" v-model="device"
                                :disabled="profile.sounds.system != 'aplay'">
                            <option value="">Default Device</option>
                            <option v-for="(desc, id) in speakers" :value="id" v-bind:key="id">{{ id }}: {{ desc }}</option>
                        </select>
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="sounds-system" id="sounds-system-mqtt" value="hermes" v-model="profile.sounds.system">
                        <label class="form-check-label" for="sounds-system-mqtt">
                            Play sound remotely with MQTT (<a href="https://docs.snips.ai/reference/hermes">Hermes protocol</a>)
                        </label>
                    </div>
                </div>
                <div class="form-row">
                    <div class="col text-muted">
                        Rhasspy will publish WAV data on: <tt>hermes/audioServer/{{ this.profile.mqtt.site_id }}/playBytes/&lt;REQUEST_ID&gt;</tt>
                        <div class="alert alert-danger" v-if="profile.sounds.system == 'hermes' && !profile.mqtt.enabled">
                            MQTT is not enabled
                        </div>
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row bg-info text-white pt-2 pl-2">
                    <h4 id="profile-sounds">Sounds</h4>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <p class="text-muted">WAV files to play when Rhasspy wakes up and is finished recording a voice command.</p>
                </div>
                <div class="form-row">
                    <p class="text-muted">Use <tt>${RHASSPY_PROFILE_DIR}</tt> for your profile directory.</p>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="sounds-wake" class="col-form-label">Wake WAV</label>
                    <div class="col">
                        <input id="sounds-wake" type="text" class="form-control" v-model="profile.sounds.wake">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="sounds-recorded" class="col-form-label">Recorded WAV</label>
                    <div class="col">
                        <input id="sounds-recorded" type="text" class="form-control" v-model="profile.sounds.recorded">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="sounds-error" class="col-form-label">Error WAV</label>
                    <div class="col">
                        <input id="sounds-error" type="text" class="form-control" v-model="profile.sounds.error">
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
 import ProfileService from '@/services/ProfileService'

 export default {
     name: 'AudioPlaying',
     props: {
         profile : Object
     },
     data: function () {
         return {
             speakers: {}
         }
     },

     methods: {
         getSpeakers: function(system) {
             ProfileService.getSpeakers(system)
                           .then(request => {
                               this.speakers = request.data
                           })
                           .catch(err => this.$emit('error', err))
         }
     },

     computed: {
         device: {
            get: function() {
                if(this.profile.sounds[this.profile.sounds.system]) {
                    return this.profile.sounds[this.profile.sounds.system].device;
                }
                return "";
            },
            set: function(newValue) {
                this.profile.sounds[this.profile.sounds.system].device = newValue;
            }
         }
     },

     mounted: function() {
         this.getSpeakers();
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
