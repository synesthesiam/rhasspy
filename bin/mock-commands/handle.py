#!/usr/bin/env python

import sys
import json
import random
import datetime


def speech(text):
    global o
    o["speech"] = {"text": text}


# get json from stdin and load into python dict
o = json.loads(sys.stdin.read())

intent = o["intent"]["name"]

if intent == "GetTime":
    now = datetime.datetime.now()
    speech("It's %s %d %s." % (now.strftime('%H'), now.minute, now.strftime('%p')))

elif intent == "Hello":
    replies = ['Hi!', 'Hello!', 'Hey there!', 'Greetings.']
    speech(random.choice(replies))

# convert dict to json and print to stdout
print(json.dumps(o))
