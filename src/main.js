import Vue from 'vue'
import App from './App.vue'
import axios from 'axios'
import VueAxios from 'vue-axios'
import VueLodash from 'vue-lodash'
import VueNativeSock from 'vue-native-websocket'

Vue.use(VueAxios, axios)
Vue.use(VueLodash)

var wsProtocol = 'ws://'
if (window.location.protocol == "https:") {
    wsProtocol = 'wss://'
}

var wsURL = wsProtocol + window.location.host + '/api/events/log'
Vue.use(VueNativeSock, wsURL, {
    reconnection: true
})

import TreeView from "vue-json-tree-view"
Vue.use(TreeView)

Vue.config.productionTip = false

new Vue({
  render: h => h(App)
}).$mount('#app')
