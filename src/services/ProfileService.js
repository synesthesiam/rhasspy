import Api from '@/services/Api'

export default {
    getProfiles() {
        return Api().get('/api/profiles')
    }
}
