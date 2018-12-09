import Vue from 'vue'
import App from './App.vue'
import axios from 'axios'
import VueAxios from 'vue-axios'
import VueLodash from 'vue-lodash'

Vue.use(VueAxios, axios)
Vue.use(VueLodash)

import TreeView from "vue-json-tree-view"
Vue.use(TreeView)

Vue.config.productionTip = false

new Vue({
  render: h => h(App)
}).$mount('#app')
