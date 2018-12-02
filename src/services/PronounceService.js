import Api from '@/services/Api'

export default {
    lookupWord(profile, word) {
        return Api().post('/api/lookup', word,
                          { params: { 'profile': profile },
                            headers: { 'Content-Type': 'text/plain' } })
    },

    pronounce(profile, pronounceString, pronounceType) {
        return Api().post('/api/pronounce', pronounceString,
                          { params: { 'profile': profile, 'type': pronounceType },
                            headers: { 'Content-Type': 'text/plain' } })
    },

    download(profile, pronounceString, pronounceType) {
        return Api().post('/api/pronounce', pronounceString,
                          { params: { 'profile': profile,
                                      'type': pronounceType,
                                      'download': true },

                            headers: { 'Content-Type': 'text/plain' },
                            responseType: 'arraybuffer' })
    },

    getPhonemeExamples(profile) {
        return Api().get('/api/phonemes',
                         { params: { 'profile': profile } })
    },

    getUnknownWords(profile) {
        return Api().get('/api/unknown_words',
                         { params: { 'profile': profile } })
    },

    updateCustomWords(profile, custom_words) {
        return Api().post('/api/custom-words', custom_words,
                          { params: { 'profile': profile },
                            headers: { 'Content-Type': 'text/plain' } })
    },

    getCustomWords(profile) {
        return Api().get('/api/custom-words', { params: { 'profile': profile } })
    },
}
