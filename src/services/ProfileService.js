import Api from '@/services/Api'

export default {
    getProfiles() {
        return Api().get('/api/profiles')
    },

    getProfileSettings(layers) {
        return Api().get('/api/profile', {
            params: { 'layers': layers }
        })
    },

    updateDefaultSettings(settings) {
        if (typeof(settings) == 'object') {
            settings = JSON.stringify(settings, null, 4)
        }

        return Api().post('/api/profile', settings, {
            params: { 'layers': 'defaults' },
            headers: { 'Content-Type': 'application/json' }
        })
    },

    updateProfileSettings(settings) {
        if (typeof(settings) == 'object') {
            settings = JSON.stringify(settings, null, 4)
        }

        return Api().post('/api/profile', settings, {
            headers: { 'Content-Type': 'application/json' }
        })
    },

    getMicrophones() {
        return Api().get('/api/microphones')
    },

    testMicrophones() {
        return Api().get('/api/test-microphones')
    }
}
