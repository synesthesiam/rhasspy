import Api from '@/services/Api'

export default {
    transcribeWav(wavData, sendHass) {
        var params = {}
        if (!sendHass) {
            params['nohass'] = true
        }

        return Api().post('/api/speech-to-intent', wavData,
                          { params: params,
                            headers: { 'Content-Type': 'audio/wav' } })
    },

    getIntent(sentence, sendHass) {
        var params = {}
        if (!sendHass) {
            params['nohass'] = true
        }

        return Api().post('/api/text-to-intent', sentence,
                          { params: params,
                            headers: { 'Content-Type': 'text/plain' } })
    },

    startRecording() {
        return Api().post('/api/start-recording', '')
    },

    stopRecording(sendHass) {
        var params = {}
        if (!sendHass) {
            params['nohass'] = true
        }

        return Api().post('/api/stop-recording', '',
                          { params: params })
    },

    wakeup() {
        return Api().post('/api/listen-for-command')
    }
}
