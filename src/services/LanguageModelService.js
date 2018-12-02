import Api from '@/services/Api'

export default {
    update_sentences(profile, sentences) {
        return Api().post('/api/sentences', sentences,
                          { params: { 'profile': profile },
                            headers: { 'Content-Type': 'text/plain' } })
    },

    getSentences(profile) {
        return Api().get('/api/sentences', { params: { 'profile': profile } })
    },

    train(profile) {
        return new Api().post('/api/train', '',
                              { params: { 'profile': profile }})
    },

    reload(profile) {
        return new Api().post('/api/reload', '',
                              { params: { 'profile': profile }})
    }
}
