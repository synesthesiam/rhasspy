import Api from '@/services/Api'

export default {
    getProfiles() {
        return Api().get('/api/profiles')
    },

    getProfileSettings(profile) {
        return Api().get('/api/profile', { params: { 'profile': profile } })
    }
}
