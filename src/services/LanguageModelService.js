import Api from '@/services/Api'

export default {
    update_sentences(sentences) {
        return Api().post('/api/sentences', sentences,
                          { headers: { 'Content-Type': 'application/json' } })
    },

    getSentences() {
        return Api().get('/api/sentences',
                         { headers: { 'Accept': 'application/json' } })
    },

    update_slots(slots) {
        return Api().post('/api/slots', slots,
                          { params: { 'overwrite_all': 'true' },
                            headers: { 'Content-Type': 'application/json' } })
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
