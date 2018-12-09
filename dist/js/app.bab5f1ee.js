(function(t){function e(e){for(var n,o,i=e[0],c=e[1],l=e[2],u=0,p=[];u<i.length;u++)o=i[u],a[o]&&p.push(a[o][0]),a[o]=0;for(n in c)Object.prototype.hasOwnProperty.call(c,n)&&(t[n]=c[n]);d&&d(e);while(p.length)p.shift()();return r.push.apply(r,l||[]),s()}function s(){for(var t,e=0;e<r.length;e++){for(var s=r[e],n=!0,i=1;i<s.length;i++){var c=s[i];0!==a[c]&&(n=!1)}n&&(r.splice(e--,1),t=o(o.s=s[0]))}return t}var n={},a={app:0},r=[];function o(e){if(n[e])return n[e].exports;var s=n[e]={i:e,l:!1,exports:{}};return t[e].call(s.exports,s,s.exports,o),s.l=!0,s.exports}o.m=t,o.c=n,o.d=function(t,e,s){o.o(t,e)||Object.defineProperty(t,e,{enumerable:!0,get:s})},o.r=function(t){"undefined"!==typeof Symbol&&Symbol.toStringTag&&Object.defineProperty(t,Symbol.toStringTag,{value:"Module"}),Object.defineProperty(t,"__esModule",{value:!0})},o.t=function(t,e){if(1&e&&(t=o(t)),8&e)return t;if(4&e&&"object"===typeof t&&t&&t.__esModule)return t;var s=Object.create(null);if(o.r(s),Object.defineProperty(s,"default",{enumerable:!0,value:t}),2&e&&"string"!=typeof t)for(var n in t)o.d(s,n,function(e){return t[e]}.bind(null,n));return s},o.n=function(t){var e=t&&t.__esModule?function(){return t["default"]}:function(){return t};return o.d(e,"a",e),e},o.o=function(t,e){return Object.prototype.hasOwnProperty.call(t,e)},o.p="/";var i=window["webpackJsonp"]=window["webpackJsonp"]||[],c=i.push.bind(i);i.push=e,i=i.slice();for(var l=0;l<i.length;l++)e(i[l]);var d=c;r.push([0,"chunk-vendors"]),s()})({0:function(t,e,s){t.exports=s("56d7")},"034f":function(t,e,s){"use strict";var n=s("c21b"),a=s.n(n);a.a},"147d":function(t,e,s){},"3c65":function(t,e,s){},"56d7":function(t,e,s){"use strict";s.r(e);s("cadf"),s("551c"),s("097d");var n=s("795d"),a=function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{attrs:{id:"app"}},[s("nav",{staticClass:"navbar navbar-expand-md navbar-dark bg-dark fixed-top"},[s("div",{staticClass:"navbar-container"},[s("img",{staticClass:"navbar-brand",class:t.spinnerClass,attrs:{src:"/img/microphone.png"}}),s("a",{staticClass:"text-white font-weight-bold",attrs:{href:"/"}},[t._v("Rhasspy Voice Assistant")]),s("a",{staticClass:"badge badge-info ml-2",attrs:{href:"/api/"}},[t._v("API")])]),s("div",{staticClass:"navbar-container ml-auto"},[s("label",{staticClass:"text-white",attrs:{for:"profiles"}},[t._v("Profile:")]),s("select",{directives:[{name:"model",rawName:"v-model",value:t.profile,expression:"profile"}],staticClass:"ml-2",attrs:{id:"profiles"},on:{change:function(e){var s=Array.prototype.filter.call(e.target.options,function(t){return t.selected}).map(function(t){var e="_value"in t?t._value:t.value;return e});t.profile=e.target.multiple?s:s[0]}}},[s("option",{attrs:{disabled:"",value:""}},[t._v("Select Profile")]),t._l(t.profiles,function(e){return s("option",{key:e},[t._v(t._s(e))])})],2),s("button",{staticClass:"btn btn-success ml-3",attrs:{disabled:this.training},on:{click:t.train}},[t._v("Re-Train")]),s("button",{staticClass:"btn btn-info ml-3",on:{click:t.reload}},[t._v("Reload")])])]),s("div",{staticClass:"main-container"},[t.hasAlert?s("div",{staticClass:"alert",class:t.alertClass,attrs:{role:"alert"}},[t._v("\n            "+t._s(t.alertText)+"\n        ")]):t._e(),t._m(0),s("div",{staticClass:"tab-content",attrs:{id:"myTabContent"}},[s("div",{staticClass:"tab-pane fade show active",attrs:{id:"speech",role:"tabpanel","aria-labelledby":"speech-tab"}},[s("TranscribeSpeech",{attrs:{profile:t.profile}})],1),s("div",{staticClass:"tab-pane fade",attrs:{id:"language",role:"tabpanel","aria-labelledby":"language-tab"}},[s("TrainLanguageModel",{attrs:{profile:t.profile}})],1),s("div",{staticClass:"tab-pane fade",attrs:{id:"pronounce",role:"tabpanel","aria-labelledby":"pronounce-tab"}},[s("LookupPronounce",{attrs:{profile:t.profile,unknownWords:t.unknownWords}})],1),s("div",{staticClass:"tab-pane fade",attrs:{id:"settings",role:"tabpanel","aria-labelledby":"settings-tab"}},[s("ProfileSettings",{attrs:{profile:t.profile,profiles:t.profiles}})],1)])])])},r=[function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("ul",{staticClass:"nav nav-tabs",attrs:{id:"myTab",role:"tablist"}},[s("li",{staticClass:"nav-item"},[s("a",{staticClass:"nav-link active",attrs:{id:"speech-tab","data-toggle":"tab",href:"#speech",role:"tab","aria-controls":"speech","aria-selected":"false"}},[t._v("Speech")])]),s("li",{staticClass:"nav-item"},[s("a",{staticClass:"nav-link",attrs:{id:"language-tab","data-toggle":"tab",href:"#language",role:"tab","aria-controls":"language","aria-selected":"false"}},[t._v("Sentences")])]),s("li",{staticClass:"nav-item"},[s("a",{staticClass:"nav-link",attrs:{id:"pronounce-tab","data-toggle":"tab",href:"#pronounce",role:"tab","aria-controls":"pronounce","aria-selected":"true"}},[t._v("Words")])]),s("li",{staticClass:"nav-item"},[s("a",{staticClass:"nav-link",attrs:{id:"settings-tab","data-toggle":"tab",href:"#settings",role:"tab","aria-controls":"settings","aria-selected":"true"}},[t._v("Settings")])])])}],o=(s("55dd"),s("ac6a"),s("ffc1"),s("bc3a")),i=s.n(o),c=function(){var t={};return Object({NODE_ENV:"production",BASE_URL:"/"}).VUE_APP_BASE_URL&&(t.baseURL=Object({NODE_ENV:"production",BASE_URL:"/"}).VUE_APP_BASE_URL),i.a.create(t)},l={getProfiles:function(){return c().get("/api/profiles")},getProfileSettings:function(t,e){return c().get("/api/profile",{params:{profile:t,layers:e}})},updateProfileSettings:function(t,e){return c().post("/api/profile",JSON.stringify(e,null,4),{params:{profile:t},headers:{"Content-Type":"application/json"}})}},d={update_sentences:function(t,e){return c().post("/api/sentences",e,{params:{profile:t},headers:{"Content-Type":"text/plain"}})},getSentences:function(t){return c().get("/api/sentences",{params:{profile:t}})},train:function(t){return(new c).post("/api/train","",{params:{profile:t}})},reload:function(t){return(new c).post("/api/reload","",{params:{profile:t}})}},u={lookupWord:function(t,e){return c().post("/api/lookup",e,{params:{profile:t},headers:{"Content-Type":"text/plain"}})},pronounce:function(t,e,s){return c().post("/api/pronounce",e,{params:{profile:t,type:s},headers:{"Content-Type":"text/plain"}})},download:function(t,e,s){return c().post("/api/pronounce",e,{params:{profile:t,type:s,download:!0},headers:{"Content-Type":"text/plain"},responseType:"arraybuffer"})},getPhonemeExamples:function(t){return c().get("/api/phonemes",{params:{profile:t}})},getUnknownWords:function(t){return c().get("/api/unknown_words",{params:{profile:t}})},updateCustomWords:function(t,e){return c().post("/api/custom-words",e,{params:{profile:t},headers:{"Content-Type":"text/plain"}})},getCustomWords:function(t){return c().get("/api/custom-words",{params:{profile:t}})}},p=function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{staticClass:"container"},[s("p",[t._v("\n        You can look up a word in the dictionary below, or have the system guess how an unknown word is pronounced.\n    ")]),s("p",[t._v("\n        New words should be added to the CMU dictionary in your profile (usually "),s("tt",[t._v("custom_words.txt")]),t._v(").\n    ")],1),s("form",{staticClass:"form",on:{submit:function(e){return e.preventDefault(),t.lookupWord(e)}}},[s("div",{staticClass:"form-row form-group"},[t._m(0),s("div",{staticClass:"col"},[s("input",{directives:[{name:"model",rawName:"v-model",value:t.dictWord,expression:"dictWord"}],staticClass:"form-control",attrs:{id:"dict-word",type:"text"},domProps:{value:t.dictWord},on:{input:function(e){e.target.composing||(t.dictWord=e.target.value)}}})]),t._m(1),t._m(2),s("div",{staticClass:"col-xs-auto"},[s("select",{directives:[{name:"model",rawName:"v-model",value:t.phonemes,expression:"phonemes"}],staticClass:"form-control",attrs:{id:"dict-pronunciations"},on:{change:function(e){var s=Array.prototype.filter.call(e.target.options,function(t){return t.selected}).map(function(t){var e="_value"in t?t._value:t.value;return e});t.phonemes=e.target.multiple?s:s[0]}}},[s("option",{attrs:{disabled:"",value:""}},[t._v("Select Pronunciation")]),t._l(t.pronunciations,function(e){return s("option",{key:e},[t._v(t._s(e))])})],2)])]),s("div",{staticClass:"form-row form-group"},[t._m(3),s("div",{staticClass:"col"},[s("input",{directives:[{name:"model",rawName:"v-model",value:t.phonemes,expression:"phonemes"}],staticClass:"form-control",attrs:{id:"dict-phonemes",title:"Sphinx Phonemes",type:"text"},domProps:{value:t.phonemes},on:{input:function(e){e.target.composing||(t.phonemes=e.target.value)}}})]),s("div",{staticClass:"col-xs-auto"},[s("button",{staticClass:"btn btn-success",attrs:{type:"button",title:"Add to custom words"},on:{click:t.addToCustomWords}},[t._v("Add")])]),s("div",{staticClass:"col-xs-auto"},[s("input",{directives:[{name:"model",rawName:"v-model",value:t.espeakPhonemes,expression:"espeakPhonemes"}],staticClass:"form-control",attrs:{id:"espeak-phonemes",title:"eSpeak Phonemes",type:"text",readonly:""},domProps:{value:t.espeakPhonemes},on:{input:function(e){e.target.composing||(t.espeakPhonemes=e.target.value)}}})]),s("div",{staticClass:"col-xs-auto"},[s("button",{staticClass:"btn btn-secondary",attrs:{type:"button"},on:{click:t.pronouncePhonemes}},[t._v("Pronounce")])]),s("div",{staticClass:"col-xs-auto"},[s("button",{staticClass:"btn btn-info",attrs:{type:"button"},on:{click:t.downloadPhonemes}},[t._v("Download")])]),s("div",{staticClass:"col-xs-auto"},[s("select",{directives:[{name:"model",rawName:"v-model",value:t.pronounceType,expression:"pronounceType"}],staticClass:"form-control",on:{change:function(e){var s=Array.prototype.filter.call(e.target.options,function(t){return t.selected}).map(function(t){var e="_value"in t?t._value:t.value;return e});t.pronounceType=e.target.multiple?s:s[0]}}},[s("option",{attrs:{value:"phonemes"}},[t._v("Phonemes")]),s("option",{attrs:{value:"word"}},[t._v("Word")])])])])]),s("div",{staticClass:"row mt-5",attrs:{hidden:0==t.unknownWords.length}},[s("div",{staticClass:"col"},[s("h3",[t._v("Unknown Words")]),s("ul",t._l(t.unknownWords,function(e){return s("li",{key:e[0]},[s("a",{attrs:{href:"#"},on:{click:function(s){t.showUnknownWord(e[0],e[1])}}},[t._v(t._s(e[0]))])])}))])]),s("form",{staticClass:"form",on:{submit:function(e){return e.preventDefault(),t.saveCustomWords(e)}}},[s("div",{staticClass:"form-group"},[t._m(4),s("div",{staticClass:"form-group"},[s("div",{staticClass:"form-row"},[s("button",{staticClass:"btn btn-primary",class:{"btn-danger":t.customWordsDirty},attrs:{type:"submit"}},[t._v("Save Custom Words")])])]),s("div",{staticClass:"form-row"},[s("textarea",{directives:[{name:"model",rawName:"v-model",value:t.customWords,expression:"customWords"}],staticClass:"form-control",class:{"border-danger":t.customWordsDirty},staticStyle:{"border-width":"3px"},attrs:{id:"custom-words",type:"text",rows:"10"},domProps:{value:t.customWords},on:{input:[function(e){e.target.composing||(t.customWords=e.target.value)},function(e){t.customWordsDirty=!0}]}})])]),s("div",{staticClass:"form-group"},[s("div",{staticClass:"form-row"},[s("button",{staticClass:"btn btn-primary",class:{"btn-danger":t.customWordsDirty},attrs:{type:"submit"}},[t._v("Save Custom Words")])])])]),t._m(5),s("div",{staticClass:"row mt-3"},[s("div",{staticClass:"col"},[s("table",{staticClass:"table"},[t._m(6),s("tbody",t._l(t.examples,function(e){return s("tr",{key:e[0]},[s("td",[t._v(t._s(e[0]))]),s("td",[t._v(t._s(e[1].word))]),s("td",[t._v(t._s(e[1].phonemes))])])}))])])])])},f=[function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{staticClass:"col-xs-auto"},[s("label",{staticClass:"col-form-label col-sm-1",attrs:{for:"dict-word"}},[t._v("Word:")])])},function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{staticClass:"col-xs-auto"},[s("button",{staticClass:"btn btn-primary form-control",attrs:{type:"submit"}},[t._v("Lookup")])])},function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{staticClass:"col-xs-auto"},[s("label",{staticClass:"col-form-label col-sm-1",attrs:{for:"dict-pronunciations"}},[t._v("Pronunciations:")])])},function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{staticClass:"col-xs-auto"},[s("label",{staticClass:"col-form-label col-sm-1",attrs:{for:"dict-phonemes"}},[t._v("Phonemes:")])])},function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{staticClass:"form-row"},[s("label",{staticClass:"col-form-label col font-weight-bold",attrs:{for:"custom-words"}},[t._v("Custom Words:")])])},function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{staticClass:"row mt-4"},[s("div",{staticClass:"col"},[s("h3",[t._v("Phonemes")]),s("p",[t._v("\n                Sphinx uses the following "),s("b",[t._v("phonemes")]),t._v(" (units of a spoken word) to describe how a\n                word is pronounced:\n            ")])])])},function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("thead",{staticClass:"thead-light"},[s("th",{attrs:{scope:"col"}},[t._v("Phoneme")]),s("th",{attrs:{scope:"col"}},[t._v("Example")]),s("th",{attrs:{scope:"col"}},[t._v("Translation")])])}],m=(s("34ef"),{name:"LookupPronounce",props:{profile:String,unknownWords:Array},data:function(){return{dictWord:"",phonemes:"",espeakPhonemes:"",pronunciations:[],examples:[],pronounceType:"phonemes",customWords:"",customWordsDirty:!1}},methods:{lookupWord:function(){var t=this;this.$parent.beginAsync(),u.lookupWord(this.profile,this.dictWord).then(function(e){e.data.in_dictionary||t.$parent.alert('"'+t.dictWord+'" not in dictionary',"warning"),t.pronunciations=e.data.pronunciations,t.pronunciations.length>0&&(t.phonemes=t.pronunciations[0]),t.espeakPhonemes=e.data.espeak_phonemes}).catch(function(e){return t.$parent.alert(e.response.data,"danger")}).then(function(){return t.$parent.endAsync()})},showUnknownWord:function(t,e){this.dictWord=t,this.phonemes=e,this.lookupWord()},pronouncePhonemes:function(){var t=this;this.$parent.beginAsync();var e="word"==this.pronounceType?this.dictWord:this.phonemes;u.pronounce(this.profile,e,this.pronounceType).catch(function(e){return t.$parent.alert(e.response.data,"danger")}).then(function(){return t.$parent.endAsync()})},downloadPhonemes:function(){var t=this;this.$parent.beginAsync();var e="word"==this.pronounceType?this.dictWord:this.phonemes;u.download(this.profile,e,this.pronounceType).then(function(e){var s=new Uint8Array(e.data),n=window.document.createElement("a");n.href=window.URL.createObjectURL(new Blob([s],{type:"audio/wav"})),n.download=t.dictWord+".wav",document.body.appendChild(n),n.click(),document.body.removeChild(n)}).catch(function(e){return t.$parent.alert(e.response.data,"danger")}).then(function(){return t.$parent.endAsync()})},refreshExamples:function(){var t=this;u.getPhonemeExamples(this.profile).then(function(e){t.examples=Object.entries(e.data),t.examples.sort()}).catch(function(e){return t.$parent.alert(e.response.data,"danger")})},saveCustomWords:function(){var t=this;this.$parent.beginAsync(),u.updateCustomWords(this.profile,this.customWords).then(function(e){return t.$parent.alert(e.data,"success")}).catch(function(e){return t.$parent.alert(e.response.data,"danger")}).then(function(){t.$parent.endAsync(),t.customWordsDirty=!1})},getCustomWords:function(){var t=this;u.getCustomWords(this.profile).then(function(e){t.customWords=e.data}).catch(function(e){return t.$parent.alert(e.response.data,"danger")})},addToCustomWords:function(){this.dictWord.length>0&&(this.customWords+="\n"+this.dictWord+" "+this.phonemes,this.customWordsDirty=!0)}},mounted:function(){this.refreshExamples(),this.customWords=this.getCustomWords()},watch:{profile:function(){this.refreshExamples(),this.customWords=this.getCustomWords()}}}),h=m,v=(s("8c8a"),s("2877")),g=Object(v["a"])(h,p,f,!1,null,"b3c42c7c",null);g.options.__file="LookupPronounce.vue";var _=g.exports,b=function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{staticClass:"container"},[s("form",{staticClass:"form",on:{submit:function(e){return e.preventDefault(),t.saveSentences(e)}}},[s("div",{staticClass:"form-group"},[t._m(0),t._m(1),s("div",{staticClass:"form-row text-muted pl-1"},[s("p",[t._v("Sentences shouldn't contain non-words characters like commas and periods. Rules have an "),s("tt",[t._v("=")]),t._v(" and optionally a "),s("tt",[t._v("{tag}")]),t._v(".")],1)]),s("div",{staticClass:"form-group"},[s("div",{staticClass:"form-row"},[s("button",{staticClass:"btn btn-primary",class:{"btn-danger":t.sentencesDirty},attrs:{type:"submit"}},[t._v("Save Sentences")])])]),s("div",{staticClass:"form-row"},[s("textarea",{directives:[{name:"model",rawName:"v-model",value:t.sentences,expression:"sentences"}],staticClass:"form-control",class:{"border-danger":t.sentencesDirty},staticStyle:{"border-width":"3px"},attrs:{id:"sentences",type:"text",rows:"25"},domProps:{value:t.sentences},on:{input:[function(e){e.target.composing||(t.sentences=e.target.value)},function(e){t.sentencesDirty=!0}]}})])]),s("div",{staticClass:"form-group"},[s("div",{staticClass:"form-row"},[s("button",{staticClass:"btn btn-primary",class:{"btn-danger":t.sentencesDirty},attrs:{type:"submit"}},[t._v("Save Sentences")])])])])])},C=[function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{staticClass:"form-row"},[s("label",{staticClass:"col-form-label col font-weight-bold",attrs:{for:"sentences"}},[t._v("Intent Examples:")])])},function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{staticClass:"form-row text-muted pl-1"},[s("p",[t._v("Example sentences, formatted "),s("a",{attrs:{href:"https://docs.python.org/3/library/configparser.html"}},[t._v("ini style")]),t._v(", with each section (intent) containing a simplified "),s("a",{attrs:{href:"https://www.w3.org/TR/jsgf/"}},[t._v("JSGF Grammar")]),t._v(".")])])}],y={name:"TrainLangaugeModel",props:{profile:String},data:function(){return{sentences:"",sentencesDirty:!1}},methods:{saveSentences:function(){var t=this;this.$parent.beginAsync(),d.update_sentences(this.profile,this.sentences).then(function(e){return t.$parent.alert(e.data,"success")}).catch(function(e){return t.$parent.alert(e.response.data,"danger")}).then(function(){t.$parent.endAsync(),t.sentencesDirty=!1})},getSentences:function(){var t=this;d.getSentences(this.profile).then(function(e){t.sentences=e.data}).catch(function(e){return t.$parent.alert(e.response.data,"danger")})}},mounted:function(){this.sentences=this.getSentences()},watch:{profile:function(){this.sentences=this.getSentences()}}},w=y,S=(s("aa5e"),Object(v["a"])(w,b,C,!1,null,"6f3633aa",null));S.options.__file="TrainLanguageModel.vue";var x=S.exports,k=function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{staticClass:"container"},[s("form",{staticClass:"form",on:{submit:function(e){return e.preventDefault(),t.getIntent(e)}}},[s("div",{staticClass:"form-group"},[s("div",{staticClass:"form-row"},[t._m(0),s("div",{staticClass:"col-auto"},[s("select",{directives:[{name:"model",rawName:"v-model",value:t.device,expression:"device"}],attrs:{id:"device"},on:{change:function(e){var s=Array.prototype.filter.call(e.target.options,function(t){return t.selected}).map(function(t){var e="_value"in t?t._value:t.value;return e});t.device=e.target.multiple?s:s[0]}}},[s("option",{attrs:{value:"-1"}},[t._v("Default Device")]),t._l(t.microphones,function(e,n){return s("option",{key:n,domProps:{value:n}},[t._v(t._s(n)+": "+t._s(e))])})],2)]),s("div",{staticClass:"col-auto"},[s("button",{staticClass:"btn",class:{"btn-danger":t.recording,"btn-primary":!t.recording},attrs:{type:"button",disabled:t.interpreting},on:{mousedown:t.startRecording,mouseup:t.stopRecording}},[t._v(t._s(t.recording?"Release to Stop":"Hold to Record"))])])])]),s("div",{staticClass:"form-group"},[s("div",{staticClass:"form-row"},[t._m(1),s("div",{staticClass:"col"},[s("input",{ref:"wavFile",staticClass:"form-control",attrs:{id:"wavFile",type:"file"}})]),s("div",{staticClass:"col-auto"},[s("button",{staticClass:"btn btn-info",attrs:{type:"button"},on:{click:t.transcribe}},[t._v("Transcribe WAV")])])]),t._m(2)]),s("div",{staticClass:"form-group"},[s("div",{staticClass:"form-row"},[t._m(3),s("div",{staticClass:"col"},[s("input",{directives:[{name:"model",rawName:"v-model",value:t.sentence,expression:"sentence"}],staticClass:"form-control",attrs:{id:"sentence",type:"text"},domProps:{value:t.sentence},on:{input:function(e){e.target.composing||(t.sentence=e.target.value)}}})]),t._m(4)])]),s("div",{staticClass:"form-group"},[s("div",{staticClass:"form-row mt-5"},[s("div",{staticClass:"col-auto"},[s("input",{directives:[{name:"model",rawName:"v-model",value:t.sendHass,expression:"sendHass"}],attrs:{type:"checkbox",id:"sendHass"},domProps:{checked:Array.isArray(t.sendHass)?t._i(t.sendHass,null)>-1:t.sendHass},on:{change:function(e){var s=t.sendHass,n=e.target,a=!!n.checked;if(Array.isArray(s)){var r=null,o=t._i(s,r);n.checked?o<0&&(t.sendHass=s.concat([r])):o>-1&&(t.sendHass=s.slice(0,o).concat(s.slice(o+1)))}else t.sendHass=a}}}),s("label",{staticClass:"ml-1",attrs:{for:"sendHass"}},[t._v("Send to Home Assistant")])])])]),s("hr"),s("div",{staticClass:"form-group"},[s("div",{staticClass:"form-row mt-5"},[s("div",[s("tree-view",{attrs:{data:t.jsonSource,options:{rootObjectKey:"intent"},hidden:!t.jsonSource}})],1)])])])])},P=[function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{staticClass:"col-auto"},[s("label",{staticClass:"col-form-label col",attrs:{for:"device"}},[t._v("Audio Device")])])},function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{staticClass:"col-auto"},[s("label",{staticClass:"col-form-label col",attrs:{for:"wavFile"}},[t._v("WAV file")])])},function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{staticClass:"form-row"},[s("p",{staticClass:"text-muted mt-1"},[t._v("\n                    16-bit 16Khz mono preferred\n                ")])])},function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{staticClass:"col-auto"},[s("label",{staticClass:"col-form-label col",attrs:{for:"sentence"}},[t._v("Sentence")])])},function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{staticClass:"col-auto"},[s("button",{staticClass:"btn btn-secondary",attrs:{type:"submit"}},[t._v("Get Intent")])])}],W=(s("7f7f"),{transcribeWav:function(t,e,s){var n={profile:t};return s||(n["nohass"]=!0),c().post("/api/speech-to-intent",e,{params:n,headers:{"Content-Type":"audio/wav"}})},getIntent:function(t,e,s){var n={profile:t};return s||(n["nohass"]=!0),c().post("/api/text-to-intent",e,{params:n,headers:{"Content-Type":"text/plain"}})},startRecording:function(t,e){return c().post("/api/start-recording","",{params:{profile:t,device:e}})},stopRecording:function(t,e){var s={profile:t};return e||(s["nohass"]=!0),c().post("/api/stop-recording","",{params:s})},getMicrophones:function(t){return c().get("/api/microphones",{params:{profile:t}})}}),T={name:"TranscribeSpeech",props:{profile:String},data:function(){return{jsonSource:null,sentence:"",recording:!1,interpreting:!1,device:"-1",microphones:{},sendHass:!0}},methods:{transcribe:function(){this.sentence="";var t=new FileReader,e=this;t.onload=function(){e.$parent.beginAsync(),W.transcribeWav(e.profile,this.result,e.sendHass).then(function(t){e.$parent.alert("Got intent: "+t.data.intent.name+" in "+t.data.time_sec.toFixed(2)+" second(s)","success"),e.sentence=t.data.text,e.jsonSource=t.data}).catch(function(t){return e.$parent.alert(t.response.data,"danger")}).then(function(){return e.$parent.endAsync()})};var s=this.$refs.wavFile.files;s.length>0?t.readAsArrayBuffer(s[0]):this.$parent.alert("No WAV file","danger")},getIntent:function(){var t=this;this.$parent.beginAsync(),W.getIntent(this.profile,this.sentence,this.sendHass).then(function(e){e.data.error?t.$parent.alert(e.data.error,"danger"):t.$parent.alert("Got intent: "+e.data.intent.name+" in "+e.data.time_sec.toFixed(2)+" second(s)","success"),t.jsonSource=e.data}).catch(function(e){return t.$parent.alert(e.response.data,"danger")}).then(function(){return t.$parent.endAsync()})},startRecording:function(){var t=this;W.startRecording(this.profile,this.device).then(function(){t.recording=!0}).catch(function(e){return t.$parent.alert(e.response.data,"danger")})},stopRecording:function(){var t=this;this.interpreting=!0,this.$parent.beginAsync(),W.stopRecording(this.profile,this.sendHass).then(function(e){t.recording=!1,t.jsonSource=e.data,t.sentence=e.data.text}).catch(function(e){return t.$parent.alert(e.response.data,"danger")}).then(function(){t.recording=!1,t.interpreting=!1,t.$parent.endAsync()})}},mounted:function(){var t=this;W.getMicrophones(this.profile).then(function(e){t.microphones=e.data}).catch(function(e){return t.$parent.alert(e.response.data,"danger")})}},$=T,A=(s("eba8"),Object(v["a"])($,k,P,!1,null,"43b9211b",null));A.options.__file="TranscribeSpeech.vue";var R=A.exports,U=function(){var t=this,e=t.$createElement,s=t._self._c||e;return s("div",{staticClass:"container"},[s("form",{staticClass:"form",on:{submit:function(e){return e.preventDefault(),t.saveSettings(e)}}},[s("h2",[t._v(t._s(this.profile))]),s("button",{staticClass:"btn btn-primary"},[t._v("Save Settings")]),s("div",{staticClass:"card mt-3"},[s("div",{staticClass:"card-header"},[t._v("Home Assistant")]),s("div",{staticClass:"card-body"},[s("div",{staticClass:"form-group"},[s("div",{staticClass:"form-row"},[s("label",{staticClass:"col-form-label",attrs:{for:"hass-url"}},[t._v("Hass URL")]),s("div",{staticClass:"col"},[s("input",{directives:[{name:"model",rawName:"v-model",value:t.hassURL,expression:"hassURL"}],staticClass:"form-control",attrs:{id:"hass-url",type:"text"},domProps:{value:t.hassURL},on:{input:function(e){e.target.composing||(t.hassURL=e.target.value)}}})])])]),s("div",{staticClass:"form-group"},[s("div",{staticClass:"form-row"},[s("label",{staticClass:"col-form-label",attrs:{for:"hass-password"}},[t._v("API Password")]),s("div",{staticClass:"col"},[s("input",{directives:[{name:"model",rawName:"v-model",value:t.hassPassword,expression:"hassPassword"}],staticClass:"form-control",attrs:{id:"hass-password",type:"text"},domProps:{value:t.hassPassword},on:{input:function(e){e.target.composing||(t.hassPassword=e.target.value)}}})])])])])]),s("div",{staticClass:"card mt-3"},[s("div",{staticClass:"card-header"},[t._v("Speech Recognition")]),s("div",{staticClass:"card-body"},[s("div",{staticClass:"form-group"},[s("div",{staticClass:"form-row"},[s("div",{staticClass:"form-check"},[s("input",{directives:[{name:"model",rawName:"v-model",value:t.rhasspySTT,expression:"rhasspySTT"}],staticClass:"form-check-input",attrs:{type:"radio",name:"localSTT",id:"local-stt",value:"local"},domProps:{checked:t._q(t.rhasspySTT,"local")},on:{change:function(e){t.rhasspySTT="local"}}}),s("label",{staticClass:"form-check-label",attrs:{for:"local-stt"}},[t._v("\n                                Do speech recognition on this device\n                            ")])])]),s("div",{staticClass:"form-row"},[s("div",{staticClass:"form-check"},[s("input",{directives:[{name:"model",rawName:"v-model",value:t.rhasspySTT,expression:"rhasspySTT"}],staticClass:"form-check-input",attrs:{type:"radio",name:"remoteSTT",id:"remote-stt",value:"remote"},domProps:{checked:t._q(t.rhasspySTT,"remote")},on:{change:function(e){t.rhasspySTT="remote"}}}),s("label",{staticClass:"form-check-label",attrs:{for:"remote-stt"}},[t._v("\n                                Use remote Rhasspy server for speech recognition\n                            ")])])])]),s("div",{staticClass:"form-group"},[s("div",{staticClass:"form-row"},[s("label",{staticClass:"col-form-label",attrs:{for:"stt-url"}},[t._v("Rhasspy Speech-to-Text URL")]),s("div",{staticClass:"col"},[s("input",{directives:[{name:"model",rawName:"v-model",value:t.sttURL,expression:"sttURL"}],staticClass:"form-control",attrs:{id:"stt-url",type:"text",disabled:"local"==t.rhasspySTT},domProps:{value:t.sttURL},on:{input:function(e){e.target.composing||(t.sttURL=e.target.value)}}})])])])])]),s("div",{staticClass:"card mt-3"},[s("div",{staticClass:"card-header"},[t._v("Intent Recognition")]),s("div",{staticClass:"card-body"},[s("div",{staticClass:"form-group"},[s("div",{staticClass:"form-row"},[s("div",{staticClass:"form-check"},[s("input",{directives:[{name:"model",rawName:"v-model",value:t.rhasspyIntent,expression:"rhasspyIntent"}],staticClass:"form-check-input",attrs:{type:"radio",name:"localIntent",id:"local-intent",value:"local"},domProps:{checked:t._q(t.rhasspyIntent,"local")},on:{change:function(e){t.rhasspyIntent="local"}}}),s("label",{staticClass:"form-check-label",attrs:{for:"local-intent"}},[t._v("\n                                Do intent recognition on this device\n                            ")])])]),s("div",{staticClass:"form-row"},[s("div",{staticClass:"form-check"},[s("input",{directives:[{name:"model",rawName:"v-model",value:t.rhasspyIntent,expression:"rhasspyIntent"}],staticClass:"form-check-input",attrs:{type:"radio",name:"remoteIntent",id:"remote-intent",value:"remote"},domProps:{checked:t._q(t.rhasspyIntent,"remote")},on:{change:function(e){t.rhasspyIntent="remote"}}}),s("label",{staticClass:"form-check-label",attrs:{for:"remote-intent"}},[t._v("\n                                Use remote Rhasspy server for intent recognition\n                            ")])])])]),s("div",{staticClass:"form-group"},[s("div",{staticClass:"form-row"},[s("label",{staticClass:"col-form-label",attrs:{for:"intent-url"}},[t._v("Rhasspy Text-to-Intent URL")]),s("div",{staticClass:"col"},[s("input",{directives:[{name:"model",rawName:"v-model",value:t.intentURL,expression:"intentURL"}],staticClass:"form-control",attrs:{id:"intent-url",type:"text",disabled:"local"==t.rhasspyIntent},domProps:{value:t.intentURL},on:{input:function(e){e.target.composing||(t.intentURL=e.target.value)}}})])])])])]),s("button",{staticClass:"btn btn-primary mt-3"},[t._v("Save Settings")]),s("h2",{staticClass:"mt-5"},[t._v("Current")]),s("div",{staticClass:"card"},[s("div",{staticClass:"card-header"},[t._v("\n                Current settings for "+t._s(this.profile)+"\n            ")]),s("div",{staticClass:"card-body"},[s("tree-view",{attrs:{data:t.profileSettings,options:{rootObjectKey:"current"},hidden:!t.profileSettings}})],1)]),s("h2",{staticClass:"mt-5"},[t._v("Defaults")]),s("div",{staticClass:"card"},[s("div",{staticClass:"card-header"},[t._v("\n                Default settings for all profiles\n            ")]),s("div",{staticClass:"card-body"},[s("tree-view",{attrs:{data:t.defaultSettings,options:{rootObjectKey:"defaults"},hidden:!t.defaultSettings}})],1)])])])},L=[],E={name:"ProfileSettings",props:{profile:String,profiles:Array},data:function(){return{profileSettings:{},defaultSettings:{},defaultProfile:"",hassURL:"",hassPassword:"",rhasspySTT:"local",sttURL:"",rhasspyIntent:"local",intentURL:""}},methods:{refreshSettings:function(){var t=this;l.getProfileSettings(this.profile,"profile").then(function(e){t.profileSettings=e.data,t.defaultProfile=t._.get(t.profileSettings,"rhasspy.default_profile",t.defaultSettings.rhasspy.default_profile),t.hassURL=t._.get(t.profileSettings,"home_assistant.url",t.defaultSettings.home_assistant.url),t.hassPassword=t._.get(t.profileSettings,"home_assistant.api_password",t.defaultSettings.home_assistant.api_password);var s=t._.get(t.profileSettings,"speech_to_text.system",t.defaultSettings.speech_to_text.system);t.sttRemote="remote"==s?"remote":"local",t.sttURL=t._.get(t.profileSettings,"speech_to_text.remote.url",t.defaultSettings.speech_to_text.remote.url);var n=t._.get(t.profileSettings,"intent.system",t.defaultSettings.intent.system);t.intentRemote="remote"==n?"remote":"local",t.intentURL=t._.get(t.profileSettings,"intent.remote.url",t.defaultSettings.intent.remote.url)}).catch(function(e){return t.$parent.alert(e.response.data,"danger")})},refreshDefaults:function(){var t=this;l.getProfileSettings(this.profile,"defaults").then(function(e){t.defaultSettings=e.data}).catch(function(e){return t.$parent.alert(e.response.data,"danger")})},saveSettings:function(){var t=this;this._.set(this.profileSettings,"home_assistant.url",this.hassURL),this._.set(this.profileSettings,"home_assistant.api_password",this.hassPassword),"remote"==this.rhasspySTT?(this._.set(this.profileSettings,"speech_to_text.system","remote"),this._.set(this.profileSettings,"speech_to_text.remote.url",this.sttURL)):this._.set(this.profileSettings,"speech_to_text.system",this._.get(this.defaultSettings,"speech_to_text.system","pocketsphinx")),"remote"==this.rhasspyIntent?(this._.set(this.profileSettings,"intent.system","remote"),this._.set(this.profileSettings,"intent.remote.url",this.intentURL)):this._.set(this.profileSettings,"intent.system",this._.get(this.defaultSettings,"intent.system","fuzzywuzzy")),this.$parent.beginAsync(),l.updateProfileSettings(this.profile,this.profileSettings).then(function(e){return t.$parent.alert(e.data,"success")}).catch(function(e){return t.$parent.alert(e.response.data,"danger")}).then(function(){t.$parent.endAsync()})}},mounted:function(){this.refreshDefaults(),this.refreshSettings()},watch:{profile:function(){this.refreshDefaults(),this.refreshSettings()}}},D=E,j=(s("7e56"),Object(v["a"])(D,U,L,!1,null,"25d68e6b",null));j.options.__file="ProfileSettings.vue";var N=j.exports,O={name:"app",components:{LookupPronounce:_,TrainLanguageModel:x,TranscribeSpeech:R,ProfileSettings:N},data:function(){return{hasAlert:!1,alertText:"",alertClass:"alert-info",spinnerClass:"",profile:"en",profiles:[],training:!1,unknownWords:[]}},methods:{startSpinning:function(){this.spinnerClass="spinner"},stopSpinning:function(){this.spinnerClass=""},clearAlert:function(){this.hasAlert=!1,this.alertText="",this.alertClass="alert-info"},alert:function(t,e){this.hasAlert=!0,this.alertText=t,this.alertClass="alert-"+e},beginAsync:function(){this.clearAlert(),this.startSpinning()},endAsync:function(){this.stopSpinning()},getProfiles:function(){var t=this;l.getProfiles().then(function(e){t.profile=e.data.default_profile,t.profiles=e.data.profiles}).catch(function(e){return t.alert(e.response.data,"danger")})},train:function(){var t=this;this.beginAsync(),this.training=!0,d.train(this.profile).then(function(e){return t.alert(e.data,"success")}).catch(function(e){return t.alert(e.response.data,"danger")}).then(function(){t.training=!1,t.getUnknownWords(),t.endAsync()})},reload:function(){var t=this;d.reload(this.profile).then(function(e){return t.alert(e.data,"success")}).catch(function(e){return t.alert(e.response.data,"danger")})},getUnknownWords:function(){var t=this;u.getUnknownWords(this.profile).then(function(e){t.unknownWords=Object.entries(e.data),t.unknownWords.sort()}).catch(function(e){return t.alert(e.response.data,"danger")})}},mounted:function(){this.getProfiles(),this.getUnknownWords()},watch:{profile:function(){this.getUnknownWords()}}},I=O,H=(s("034f"),Object(v["a"])(I,a,r,!1,null,null,null));H.options.__file="App.vue";var M=H.exports,F=s("a7fe"),V=s.n(F),B=s("415c"),z=s.n(B),G=s("ffde"),q=s.n(G);n["a"].use(V.a,i.a),n["a"].use(z.a),n["a"].use(q.a),n["a"].config.productionTip=!1,new n["a"]({render:function(t){return t(M)}}).$mount("#app")},"7e56":function(t,e,s){"use strict";var n=s("bc78"),a=s.n(n);a.a},"8c8a":function(t,e,s){"use strict";var n=s("c48d"),a=s.n(n);a.a},aa5e:function(t,e,s){"use strict";var n=s("147d"),a=s.n(n);a.a},bc78:function(t,e,s){},c21b:function(t,e,s){},c48d:function(t,e,s){},eba8:function(t,e,s){"use strict";var n=s("3c65"),a=s.n(n);a.a}});
//# sourceMappingURL=app.bab5f1ee.js.map