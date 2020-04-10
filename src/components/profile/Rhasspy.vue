<template>
    <div class="card mt-3">
        <div class="card-header"><i class="fas fa-crow"></i>Rhasspy</div>
        <div class="card-body">
            <div class="form-group">
                <div class="form-row">
                    <button class="btn btn-danger" @click="downloadProfile" :disabled="this.downloading">Re-Download Profile</button>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <p class="text-muted">Force Rhasspy to re-download files for the &quot;{{ this.profile.name }}&quot; profile. This will require an internet connection.</p>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <input type="checkbox" id="wake-on-start" v-model="profile.rhasspy.listen_on_start">
                    <label for="wake-on-start" class="col-form-label">Listen for wake word on start-up</label>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <input type="checkbox" id="mqtt-enabled" v-model="profile.mqtt.enabled">
                    <label for="mqtt-enabled" class="col-form-label">Enable MQTT</label>
                    <span class="col-form-label text-muted">(<a href="https://docs.snips.ai/reference/hermes">Snips.ai compatibility</a>)</span>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="mqtt-host" class="col-form-label">Host</label>
                    <div class="col-sm-auto">
                        <input id="mqtt-host" type="text" class="form-control" v-model="profile.mqtt.host" :disabled="!profile.mqtt.enabled">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="mqtt-port" class="col-form-label">Port</label>
                    <div class="col-sm-auto">
                        <input id="mqtt-port" type="text" class="form-control" v-model="profile.mqtt.port" :disabled="!profile.mqtt.enabled">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="mqtt-username" class="col-form-label">Username</label>
                    <div class="col-sm-auto">
                        <input id="mqtt-username" type="text" class="form-control" v-model="profile.mqtt.username" :disabled="!profile.mqtt.enabled">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="mqtt-password" class="col-form-label">Password</label>
                    <div class="col-sm-auto">
                        <input id="mqtt-password" type="text" class="form-control" v-model="profile.mqtt.password" :disabled="!profile.mqtt.enabled">
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="mqtt-siteid" class="col-form-label">Site ID</label>
                    <div class="col-sm-auto">
                        <input id="mqtt-siteid" type="text" class="form-control" v-model="profile.mqtt.site_id" :disabled="!profile.mqtt.enabled">
                    </div>
                    <div class="col text-muted">
                        (comma-separated)
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <input id="mqtt-tls-enabled" type="checkbox" v-model="profile.mqtt.tls.enabled" :disabled="!profile.mqtt.enabled">
                    <label for="mqtt-tls-enabled" class="col-form-label">Enable MQTT over TLS</label>
                </div>
            </div>
            <template v-if="profile.mqtt.tls.enabled">
                <div class="form-group">
                    <div class="form-row">
                        <label for="mqtt-tls-ca_certs" class="col-form-label">ca_certs</label>
                        <div class="col-sm-auto">
                            <input id="mqtt-tls-ca_certs" type="text" class="form-control" v-model="profile.mqtt.tls.ca_certs" :disabled="!profile.mqtt.enabled">
                        </div>
                    </div>
                </div>
                <div class="form-group">
                    <div class="form-row">
                        <label for="mqtt-tls-cert_reqs" class="col-form-label">cert_reqs</label>
                        <div class="col-sm-auto">
                            <select id="mqtt-tls-cert_reqs" v-model="profile.mqtt.tls.cert_reqs" :disabled="!profile.mqtt.enabled">
                                <option value="CERT_REQUIRED" default>CERT_REQUIRED</option>
                                <option value="CERT_OPTIONAL">CERT_OPTIONAL</option>
                                <option value="CERT_NONE">CERT_NONE</option>
                            </select>
                        </div>
                    </div>
                </div>
                <div class="form-group">
                    <div class="form-row">
                        <label for="mqtt-tls-certfile" class="col-form-label">certfile</label>
                        <div class="col-sm-auto">
                            <input id="mqtt-tls-certfile" type="text" class="form-control" v-model="profile.mqtt.tls.certfile" :disabled="!profile.mqtt.enabled">
                        </div>
                    </div>
                </div>
                <div class="form-group">
                    <div class="form-row">
                        <label for="mqtt-tls-ciphers" class="col-form-label">ciphers</label>
                        <div class="col-sm-auto">
                            <input id="mqtt-tls-ciphers" type="text" class="form-control" v-model="profile.mqtt.tls.ciphers" :disabled="!profile.mqtt.enabled">
                        </div>
                    </div>
                </div>
                <div class="form-group">
                    <div class="form-row">
                        <label for="mqtt-tls-keyfile" class="col-form-label">keyfile</label>
                        <div class="col-sm-auto">
                            <input id="mqtt-tls-keyfile" type="text" class="form-control" v-model="profile.mqtt.tls.keyfile" :disabled="!profile.mqtt.enabled">
                        </div>
                    </div>
                </div>
            </template>
            <div class="form-group">
                <div class="form-row">
                    <input type="checkbox" id="mqtt-publish_intents" v-model="profile.mqtt.publish_intents" :disabled="!profile.mqtt.enabled">
                    <label for="mqtt-publish_intents" class="col-form-label">Publish intents over MQTT</label>
                </div>
                <div class="form-row">
                    <div class="col text-muted">
                        Intents will be published to <tt>hermes/intent/&lt;INTENT_NAME&gt;</tt> and <tt>rhasspy/intent/&lt;INTENT_NAME&gt;</tt>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
 import ProfileService from '@/services/ProfileService'

 export default {
     name: 'Rhasspy',
     props: {
         profile : Object,
         defaults : Object,
         profiles: Array
     },
     data: function() {
         return {
             downloading: false
         }
     },
     methods: {
         downloadProfile: function(event) {
             event.preventDefault()
             this.$emit('begin-async')
             this.downloading = true
             ProfileService.downloadProfile(true)
                           .then(() => {
                               this.$emit('restart')
                           })
                           .catch(err => this.error(err))
                           .then(() => {
                               this.downloading = false
                               this.$parent.endAsync()
                               this.$emit('end-async')
                           })
         }
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
