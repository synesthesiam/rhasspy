import Api from '@/services/Api'

export default {
    lookupWord(word) {
        return Api().post('/api/lookup', word,
                          { headers: { 'Content-Type': 'text/plain' } })
    },

    pronounce(pronounceString, pronounceType) {
        return Api().post('/api/pronounce', pronounceString,
                          { params: { 'type': pronounceType },
                            headers: { 'Content-Type': 'text/plain' } })
    },

    download(pronounceString, pronounceType) {
        return Api().post('/api/pronounce', pronounceString,
                          { params: { 'type': pronounceType,
                                      'download': true },

                            headers: { 'Content-Type': 'text/plain' },
                            responseType: 'arraybuffer' })
    },

    getPhonemeExamples() {
        return Api().get('/api/phonemes')
    },

    getUnknownWords() {
        return Api().get('/api/unknown-words')
    },

    updateCustomWords(custom_words) {
        return Api().post('/api/custom-words', custom_words,
                          { headers: { 'Content-Type': 'text/plain' } })
    },

    getCustomWords() {
        return Api().get('/api/custom-words')
    },

    saySentence(sentence) {
        return Api().post('/api/text-to-speech', sentence,
                          { headers: { 'Content-Type': 'text/plain' } })
    },
}
