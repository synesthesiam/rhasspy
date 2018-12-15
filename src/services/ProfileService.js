import Api from '@/services/Api'

export default {
    getProfiles() {
        return Api().get('/api/profiles')
    },

    getProfileSettings(profile, layers) {
        return Api().get('/api/profile', {
            params: { 'profile': profile, 'layers': layers }
        })
    },

    updateDefaultSettings(settings) {
        if (typeof(settings) == 'object') {
            settings = JSON.stringify(settings, null, 4)
        }

        return Api().post('/api/profile', settings, {
            params: { 'layers': 'default' },
            headers: { 'Content-Type': 'application/json' }
        })
    },

    updateProfileSettings(profile, settings) {
        if (typeof(settings) == 'object') {
            settings = JSON.stringify(settings, null, 4)
        }

        return Api().post('/api/profile', settings, {
            params: { 'profile': profile },
            headers: { 'Content-Type': 'application/json' }
        })
    }
}
