import axios from 'axios'

export default() => {
    var options = {}
    if (process.env.VUE_APP_BASE_URL) {
        options.baseURL = process.env.VUE_APP_BASE_URL
    }

    return axios.create(options)
}
