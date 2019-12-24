<template>
    <div class="card mt-3">
        <div class="card-header"><i class="fas fa-home"></i>Intent Handling</div>
        <div class="card-body">
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" id="handle-system-dummy" value="dummy" v-model="profile.handle.system">
                        <label class="form-check-label" v-bind:class="{ 'text-danger': profile.handle.system == 'dummy' }" for="handle-system-dummy">
                            Do not handle intents on this device
                        </label>
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" id="handle-system-hass" value="hass" v-model="profile.handle.system">
                        <label class="form-check-label" for="handle-system-hass">
                            Use Home Assistant
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="hass-url" class="col-form-label">Hass URL</label>
                    <div class="col">
                        <input id="hass-url" type="text" class="form-control" v-model="profile.home_assistant.url"
                               :disabled="profile.handle.system != 'hass'">
                    </div>
                    <div class="col text-muted">
                        Address of your Home Assistant server
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="hass-token" class="col-form-label">Access Token</label>
                    <div class="col">
                        <input id="hass-token" type="text" class="form-control" v-model="profile.home_assistant.access_token"
                               :disabled="profile.handle.system != 'hass'">
                    </div>
                    <div class="col text-muted">
                        Long-lived access token (automatically filled in Hass.IO)
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="hass-password" class="col-form-label">API Password</label>
                    <div class="col">
                        <input id="hass-password" type="text" class="form-control" v-model="profile.home_assistant.api_password"
                               :disabled="profile.handle.system != 'hass'">
                    </div>
                    <div class="col text-muted">
                        Home Assistant password (deprecated)
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" id="hass-handle-type-event" value="event" v-model="profile.home_assistant.handle_type" :disabled="profile.handle.system != 'hass'">
                        <label class="form-check-label" for="hass-handle-type-event">
                            Send <strong>events</strong> to Home Assistant (<tt>/api/events</tt>)
                        </label>
                    </div>
                </div>
                <div class="form-row">
                    <div class="col">
                        <p class="text-muted">
                            Events will be named <tt>{{ profile.home_assistant.event_type_format.replace('{0}', 'INTENT_NAME') }}</tt>
                        </p>
                    </div>
                </div>
                <div class="form-row mt-2">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" id="hass-handle-type-intent" value="intent" v-model="profile.home_assistant.handle_type" :disabled="profile.handle.system != 'hass'">
                        <label class="form-check-label" for="hass-handle-type-intent">
                            Send <strong>intents</strong> to Home Assistant (<tt>/api/intents</tt>)
                        </label>
                    </div>
                </div>
                <div class="form-row">
                    <div class="col">
                    <p class="text-muted">
                        Requires the <a href="https://www.home-assistant.io/integrations/intent/">intent component</a> in your <tt>configuration.yaml</tt>
                    </p>
                    </div>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <p class="font-weight-bold">For Self-Signed Certificates:</p>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <div class="col-auto">
                        <label for="pemPath" class="col-form-label col">PEM path</label>
                    </div>
                    <div class="col">
                        <input id="pemPath" ref="pemPath" type="text" class="form-control" v-model="profile.home_assistant.pem_file"
                               :disabled="profile.handle.system != 'hass'">
                    </div>
                    <div class="col-auto">
                        <button type="button" class="btn btn-danger"
                                @click="pemPath = ''"
                                title="Clear the PEM path (no self-signed certificate)"
                                :disabled="profile.handle.system != 'hass'">Clear</button>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <p class="muted">Full path to your <a href="http://docs.python-requests.org/en/latest/user/advanced/#ssl-cert-verification">CA_BUNDLE file or a directory with certificates of trusted CAs.</a></p>
                </div>
                <div class="form-row">
                    <p class="muted">Use <tt>$RHASSPY_PROFILE_DIR</tt> environment variable for the directory of this profile.</p>
                </div>
            </div>
            <hr>
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" id="handle-system-remote" value="remote" v-model="profile.handle.system">
                        <label class="form-check-label" for="handle-system-remote">
                            Use a remote HTTP server to handle intents
                        </label>
                    </div>
                </div>
            </div>
            <div class="form-group">
                <div class="form-row">
                    <label for="remote-handle-url" class="col-form-label">Remote URL</label>
                    <div class="col">
                        <input id="remote-handle-url" type="text" class="form-control" v-model="profile.handle.remote.url" :disabled="profile.intent.system != 'remote'">
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
 export default {
     name: 'IntentHandling',
     props: {
         profile : Object
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
