[
  {
    "id": "2f1e41c5.19c21e",
    "type": "tab",
    "label": "Rhasspy Example Flow 1",
    "disabled": false,
    "info": ""
  },
  {
    "id": "63453288.fa038c",
    "type": "websocket-listener",
    "z": "",
    "path": "ws://localhost:12101/api/events/intent",
    "wholemsg": "true"
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
        "v": "GetTime",
        "vt": "str"
      },
      {
        "t": "eq",
        "v": "ChangeLightState",
        "vt": "str"
      }
    ],
    "checkall": "true",
    "repair": false,
    "outputs": 2,
    "x": 340,
    "y": 200,
    "wires": [
      [
        "b4beb082.843988"
      ],
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
    "x": 700,
    "y": 240,
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
    "template": "Turning {{ slots.state }} the {{ slots.name }}.",
    "output": "str",
    "x": 520,
    "y": 340,
    "wires": [
      [
        "1cf9bec4.4449d1",
        "19c43cb6.6e805b"
      ]
    ]
  },
  {
    "id": "19c43cb6.6e805b",
    "type": "debug",
    "z": "2f1e41c5.19c21e",
    "name": "",
    "active": true,
    "tosidebar": true,
    "console": false,
    "tostatus": false,
    "complete": "payload",
    "targetType": "msg",
    "x": 730,
    "y": 320,
    "wires": []
  },
  {
    "id": "b4beb082.843988",
    "type": "function",
    "z": "2f1e41c5.19c21e",
    "name": "time text",
    "func": "var timeString = new Date().toLocaleTimeString([],\n{\n    hour: \"2-digit\", \n    minute: \"2-digit\",\n    hour12: true\n})\n\nreturn {\n    payload: \"It is \" + timeString\n}",
    "outputs": 1,
    "noerr": 0,
    "x": 520,
    "y": 140,
    "wires": [
      [
        "1cf9bec4.4449d1"
      ]
    ]
  }
]
