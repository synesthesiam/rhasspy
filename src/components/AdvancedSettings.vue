<template>
    <div class="container">
        <div class="text-muted pl-1">
            <p>
                You can edit <a href="https://rhasspy.readthedocs.io/en/latest/profiles/">your Rhasspy profile</a> directly here as JSON. These settings will override the defaults below.
            </p>
        </div>
        <div class="pl-1">
            <p><strong>Restart required if changes are made</strong></p>
        </div>

        <form class="form" v-on:submit.prevent="saveProfile">
            <h2>{{ this.profile }}</h2>

            <div class="form-group">
                <div class="form-row">
                    <button type="submit" class="btn btn-primary"
                            v-bind:class="{ 'btn-danger': profileSettingsDirty }">Save Profile</button>
                </div>
            </div>

            <div class="form-group">
                <div class="form-row">
                    <textarea id="profile-settings" class="form-control" style="border-width: 3px" type="text" rows="15" v-model="profileSettings" v-bind:class="{ 'border-danger': profileSettingsDirty }" @input="profileSettingsDirty=true"></textarea>
                </div>
            </div>

            <div class="form-group">
                <div class="form-row">
                    <button type="submit" class="btn btn-primary"
                            v-bind:class="{ 'btn-danger': profileSettingsDirty }">Save Profile</button>
                </div>
            </div>
        </form>

        <hr />

        <form class="form" v-on:submit.prevent="saveDefaults">
            <h2>Defaults</h2>

            <div class="text-muted pl-1">
                <p>
                    These are the default settings for all <a href="https://rhasspy.readthedocs.io/en/latest/profiles/">your Rhasspy profiles</a>. If a setting is missing in any profile, the value here will be used.
                </p>
            </div>

            <div class="form-group">
                <div class="form-row">
                    <button type="submit" class="btn btn-primary"
                            v-bind:class="{ 'btn-danger': defaultSettingsDirty }">Save Defaults</button>
                </div>
            </div>

            <textarea id="default-settings" class="form-control" type="text" rows="15" v-model="defaultSettings"></textarea>

            <div class="form-group">
                <div class="form-row pt-3">
                    <button type="submit" class="btn btn-primary"
                            v-bind:class="{ 'btn-danger': defaultSettingsDirty }">Save Defaults</button>
                </div>
            </div>
        </form>
    </div> <!-- container -->
</template>

<script>
 import ProfileService from '@/services/ProfileService'

 export default {
     name: 'AdvancedSettings',
     props: {
         profile : String
     },
     data: function () {
         return {
             profileSettings: '',
             profileSettingsDirty: false,

             defaultSettings: '',
             defaultSettingsDirty: false
         }
     },

     methods: {
         refreshSettings: function() {
             ProfileService.getProfileSettings('profile')
                           .then(request => {
                               this.profileSettings = JSON.stringify(request.data, null, 4)
                           })
                           .catch(err => this.$parent.error(err))
         },

         refreshDefaults: function() {
             ProfileService.getProfileSettings('defaults')
                           .then(request => {
                               this.defaultSettings = JSON.stringify(request.data, null, 4)
                           })
                           .catch(err => this.$parent.error(err))
         },

         saveProfile: function() {
             this.$parent.beginAsync()
             ProfileService.updateProfileSettings(this.profileSettings)
                 .then(request => this.$parent.alert(request.data, 'success'))
                 .catch(err => this.$parent.error(err))
                 .then(() => {
                     this.$parent.endAsync()
                     this.profileSettingsDirty = false
                 })
         },

         saveDefaults: function() {
             this.$parent.beginAsync()
             ProfileService.updateDefaultSettings(this.defaultSettings)
                 .then(request => this.$parent.alert(request.data, 'success'))
                 .catch(err => this.$parent.error(err))
                 .then(() => {
                     this.$parent.endAsync()
                     this.defaultSettingsDirty = false
                 })
         }
     },

     mounted: function() {
         this.refreshSettings()
         this.refreshDefaults()
     },

     watch: {
         profile() {
             this.refreshSettings()
             this.refreshDefaults()
         }
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
