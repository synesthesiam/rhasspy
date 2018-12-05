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

    updateProfileSettings(profile, settings) {
        return Api().post('/api/profile', settings, {
            params: { 'profile': profile },
            headers: { 'Content-Type': 'application/json' }
        })
    }
}
