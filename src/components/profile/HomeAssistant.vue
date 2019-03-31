<template>
    <div class="card mt-3">
        <div class="card-header"><i class="fas fa-home"></i>Home Assistant</div>
        <div class="card-body">
            <div class="form-group">
                <div class="form-row">
                    <div class="form-check">
                        <input class="form-check-input" type="radio" id="handle-system-dummy" value="dummy" v-model="profile.handle.system">
                        <label class="form-check-label" v-bind:class="{ 'text-danger': profile.handle.system == 'dummy' }" for="handle-system-dummy">
                            Do not use Home Assistant
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
        </div>
    </div>
</template>

<script>
 export default {
     name: 'HomeAssistant',
     props: {
         profile : Object
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
