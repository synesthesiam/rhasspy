import Api from '@/services/Api'

export default {
    restart() {
        return new Api().post('/api/restart', '')
    }
}
