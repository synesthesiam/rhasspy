import Api from '@/services/Api'

export default {
    transcribeWav(profile, wavData, sendHass) {
        var params = { 'profile': profile }
        if (!sendHass) {
            params['nohass'] = true
        }

        return Api().post('/api/speech-to-intent', wavData,
                          { params: params,
                            headers: { 'Content-Type': 'audio/wav' } })
    },

    getIntent(profile, sentence, sendHass) {
        var params = { 'profile': profile }
        if (!sendHass) {
            params['nohass'] = true
        }

        return Api().post('/api/text-to-intent', sentence,
                          { params: params,
                            headers: { 'Content-Type': 'text/plain' } })
    },

    startRecording(profile, device) {
        return Api().post('/api/start-recording', '',
                          { params: { 'profile': profile,
                                      'device': device } })
    },

    stopRecording(profile, sendHass) {
        var params = { 'profile': profile }
        if (!sendHass) {
            params['nohass'] = true
        }

        return Api().post('/api/stop-recording', '',
                          { params: params })
    },

    getMicrophones(profile) {
        return Api().get('/api/microphones')
    },

    testMicrophones(profile) {
        return Api().get('/api/test-microphones')
    }
}
