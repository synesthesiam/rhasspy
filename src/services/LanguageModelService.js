import Api from '@/services/Api'

export default {
    update_sentences(sentences) {
        return Api().post('/api/sentences', sentences,
                          { headers: { 'Content-Type': 'text/plain' } })
    },

    getSentences() {
        return Api().get('/api/sentences')
    },

    update_slots(slots) {
        return Api().post('/api/slots', slots,
                          { headers: { 'Content-Type': 'application/json' } })
    },

    getSlots() {
        return Api().get('/api/slots')
    },

    train(noCache) {
        var params = {}
        if (noCache) {
            params['nocache'] = 'true'
        }

        return new Api().post('/api/train', '',
                              { params: params })
    },

    reload() {
        return new Api().post('/api/reload', '')
    }
}
