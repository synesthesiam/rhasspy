import Api from '@/services/Api'

export default {
    getActorStates() {
        return Api().get('/api/actor_states')
    }
}
