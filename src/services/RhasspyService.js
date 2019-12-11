import Api from '@/services/Api'

export default {
    restart() {
        return new Api().post('/api/restart', '')
    },

    getProblems() {
        return new Api().get('/api/problems')
    },

    getVersion() {
        return new Api().get('/api/version')
    }
}
