<template>
    <div class="container">
        <div class="text-muted pl-1">
            <p>
                You can edit <a href="https://rhasspy.readthedocs.io/en/latest/profiles/">your Rhasspy profile</a> directly here as JSON.
                <br>
                Only settings that <strong>differ from the defaults</strong> are shown.
            </p>
        </div>
        <form class="form" v-on:submit.prevent="saveProfile">
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
    </div> <!-- container -->
</template>

<script>
 import ProfileService from '@/services/ProfileService'

 export default {
     name: 'AdvancedSettings',
     data: function () {
         return {
             profileSettings: '',
             profileSettingsDirty: false
         }
     },

     methods: {
         getProfile: function() {
             ProfileService.getProfileSettings('profile')
                           .then(request => {
                               this.profileSettings = JSON.stringify(request.data, null, 4)
                           })
                           .catch(err => this.error(err))
         },

         saveProfile: function() {
             this.$parent.beginAsync()
             ProfileService.updateProfileSettings(this.profileSettings)
                 .then(request => this.$parent.alert(request.data, 'success'))
                 .catch(err => this.$parent.error(err))
                 .then(() => {
                     this.$parent.endAsync()
                     this.profileSettingsDirty = false
                     if (confirm("Profile saved. Restart Rhasspy?")) {
                         this.$parent.restart()
                     }
                 })
         }
     },

     mounted: function() {
         this.getProfile()
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
