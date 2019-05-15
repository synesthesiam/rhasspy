[
  {
    "id": "d3cc2f7.a9ba6d",
    "type": "tab",
    "label": "Rhasspy Timer Example",
    "disabled": false,
    "info": ""
  },
  {
    "id": "c1e13f33.8ff9b8",
    "type": "websocket in",
    "z": "d3cc2f7.a9ba6d",
    "name": "Rhasspy Intent",
    "server": "1a023f3a.d52d69",
    "client": "",
    "x": 160,
    "y": 100,
    "wires": [
      [
        "4c28da73.cbfcbc",
        "f5900797.3a6f6"
      ]
    ]
  },
  {
    "id": "4c28da73.cbfcbc",
    "type": "debug",
    "z": "d3cc2f7.a9ba6d",
    "name": "",
    "active": true,
    "tosidebar": true,
    "console": false,
    "tostatus": false,
    "complete": "true",
    "targetType": "full",
    "x": 470,
    "y": 80,
    "wires": []
  },
  {
    "id": "f5900797.3a6f6",
    "type": "function",
    "z": "d3cc2f7.a9ba6d",
    "name": "Convert to Milliseconds",
    "func": "function splitSum(digitString) {\n    var value = 0\n    digitString.split(/\\s+/).forEach(function(digits) {\n        value += parseInt(digits)\n    })\n    \n    return value\n}\n\nhours = splitSum(msg.slots[\"hours\"] || \"0\")\nminutes = splitSum(msg.slots[\"minutes\"] || \"0\")\nseconds = splitSum(msg.slots[\"seconds\"] || \"0\")\n\nmilliseconds = 1000 * ((hours * 60 * 60) + (minutes * 60) + seconds)\n\nreturn {\n    text: \"I have \" + msg.text + \".\",\n    delay: milliseconds\n}",
    "outputs": 1,
    "noerr": 0,
    "x": 400,
    "y": 220,
    "wires": [
      [
        "461a1340.176bf4",
        "e32e60ae.b8c878"
      ]
    ]
  },
  {
    "id": "e6b3f3ab.f3c718",
    "type": "http request",
    "z": "d3cc2f7.a9ba6d",
    "name": "Text to Speech",
    "method": "POST",
    "ret": "txt",
    "paytoqs": false,
    "url": "http://localhost:12101/api/text-to-speech",
    "tls": "",
    "proxy": "",
    "authType": "basic",
    "x": 900,
    "y": 220,
    "wires": [
      []
    ]
  },
  {
    "id": "461a1340.176bf4",
    "type": "change",
    "z": "d3cc2f7.a9ba6d",
    "name": "Confirm Timer",
    "rules": [
      {
        "t": "set",
        "p": "payload",
        "pt": "msg",
        "to": "text",
        "tot": "msg"
      }
    ],
    "action": "",
    "property": "",
    "from": "",
    "to": "",
    "reg": false,
    "x": 620,
    "y": 160,
    "wires": [
      [
        "e6b3f3ab.f3c718"
      ]
    ]
  },
  {
    "id": "e32e60ae.b8c878",
    "type": "delay",
    "z": "d3cc2f7.a9ba6d",
    "name": "",
    "pauseType": "delayv",
    "timeout": "5",
    "timeoutUnits": "seconds",
    "rate": "1",
    "nbRateUnits": "1",
    "rateUnits": "second",
    "randomFirst": "1",
    "randomLast": "5",
    "randomUnits": "seconds",
    "drop": false,
    "x": 600,
    "y": 340,
    "wires": [
      [
        "a2c261fe.2a8408"
      ]
    ]
  },
  {
    "id": "a2c261fe.2a8408",
    "type": "change",
    "z": "d3cc2f7.a9ba6d",
    "name": "Timer Ready",
    "rules": [
      {
        "t": "set",
        "p": "payload",
        "pt": "msg",
        "to": "Timer is ready!",
        "tot": "str"
      }
    ],
    "action": "",
    "property": "",
    "from": "",
    "to": "",
    "reg": false,
    "x": 690,
    "y": 260,
    "wires": [
      [
        "e6b3f3ab.f3c718"
      ]
    ]
  },
  {
    "id": "1a023f3a.d52d69",
    "type": "websocket-listener",
    "z": "",
    "path": "ws://localhost:12101/api/events/intent",
    "wholemsg": "true"
  }
]
