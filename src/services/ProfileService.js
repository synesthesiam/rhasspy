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

    getMicrophones(system) {
        var params = {}
        if (system) {
            params['system'] = system
        }

        return Api().get('/api/microphones',
                         { 'params': params })
    },

    testMicrophones(system) {
        var params = {}
        if (system) {
            params['system'] = system
        }

        return Api().get('/api/test-microphones',
                         { 'params': params })
    },

    getSpeakers(system) {
        var params = {}
        if (system) {
            params['system'] = system
        }

        return Api().get('/api/speakers',
                         { 'params': params })
    },

    downloadProfile(delete_first) {
        var params = {}
        if (delete_first) {
            params['delete'] = 'true'
        }

        return Api().post('/api/download-profile', '',
                          { 'params': params })
    }
}
