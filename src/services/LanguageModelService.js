import Api from '@/services/Api'

export default {
    update_sentences(sentences) {
        return Api().post('/api/sentences', sentences,
                          { headers: { 'Content-Type': 'text/plain' } })
    },

    getSentences() {
        return Api().get('/api/sentences')
    },

    train() {
        return new Api().post('/api/train', '')
    },

    reload() {
        return new Api().post('/api/reload', '')
    }
}
