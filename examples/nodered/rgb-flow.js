[
  {
    "id": "2f1e41c5.19c21e",
    "type": "tab",
    "label": "Rhasspy Example",
    "disabled": false,
    "info": ""
  },
  {
    "id": "5b0fc170.50ca98",
    "type": "websocket in",
    "z": "2f1e41c5.19c21e",
    "name": "rhasspy",
    "server": "63453288.fa038c",
    "client": "",
    "x": 150,
    "y": 100,
    "wires": [
      [
        "7ed528d3.d8a79"
      ]
    ]
  },
  {
    "id": "7ed528d3.d8a79",
    "type": "switch",
    "z": "2f1e41c5.19c21e",
    "name": "intent filter",
    "property": "intent.name",
    "propertyType": "msg",
    "rules": [
      {
        "t": "eq",
        "v": "ChangeLightColor",
        "vt": "str"
      }
    ],
    "checkall": "true",
    "repair": false,
    "outputs": 1,
    "x": 230,
    "y": 200,
    "wires": [
      [
        "2d6e81cb.099e56"
      ]
    ]
  },
  {
    "id": "1cf9bec4.4449d1",
    "type": "http request",
    "z": "2f1e41c5.19c21e",
    "name": "text to speech",
    "method": "POST",
    "ret": "txt",
    "paytoqs": false,
    "url": "http://localhost:12101/api/text-to-speech",
    "tls": "",
    "proxy": "",
    "authType": "basic",
    "x": 440,
    "y": 340,
    "wires": [
      []
    ]
  },
  {
    "id": "2d6e81cb.099e56",
    "type": "template",
    "z": "2f1e41c5.19c21e",
    "name": "light text",
    "field": "payload",
    "fieldType": "msg",
    "format": "handlebars",
    "syntax": "mustache",
    "template": "The {{ slots.name }} is now {{ slots.color }}.",
    "output": "str",
    "x": 300,
    "y": 280,
    "wires": [
      [
        "1cf9bec4.4449d1"
      ]
    ]
  },
  {
    "id": "63453288.fa038c",
    "type": "websocket-listener",
    "z": "",
    "path": "ws://localhost:12101/api/events/intent",
    "wholemsg": "true"
  }
]
