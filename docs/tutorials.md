# Tutorials

* [RGB Light Example](#rgb-light-example)
* [Client/Server Setup](#clientserver-setup)

## RGB Light Example

Let's say you have an RGB light of some kind in your bedroom that's [hooked up already to Home Assistant](https://www.home-assistant.io/components/light.mqtt). You'd like to be able to say things like "*set the bedroom light to red*" to change its color. To start, let's write a [Home Assistant automation](https://www.home-assistant.io/docs/automation/action/) to help you out:

    automation:
      # Change the light in the bedroom to red.
      trigger:
        ...
      action:
        service: light.turn_on
        data:
          rgb_color: [255, 0, 0]
          entity_id: light.bedroom
          
Now you just need the trigger! Rhasspy will send events that can be caught with the [event trigger platform](https://www.home-assistant.io/docs/automation/trigger/#event-trigger). A different event will be sent for each *intent* that you define, with slot values corresponding to important parts of the command (like light name and color). Let's start by defining an intent in Rhasspy called `ChangeLightState` that can be said a few different ways:

    [ChangeLightState]
    colors = (red | green | blue) {color}
    set [the] (bedroom){name} [to] <colors>
    
This is a [simplified JSGF grammar](doc/sentences/md) that will generate the following sentences:

* set the bedroom to red
* set the bedroom to green
* set the bedroom to blue
* set the bedroom red
* set the bedroom green
* set the bedroom blue
* set bedroom to red
* set bedroom to green
* set bedroom to blue
* set bedroom red
* set bedroom green
* set bedroom blue

Rhasspy uses these sentences to create an [ARPA language model](https://cmusphinx.github.io/wiki/arpaformat/) for speech recognition, and also train an intent recognizer that can extract relevant parts of the command. The `{color}` tag in the `colors` rule will make Rhasspy put a `color` property in each event with the name of the recognized color (red, green, or blue). Likewise, the `{name}` tag on `bedroom` will add a `name` property to the event.

If trained on these sentences, Rhasspy will now recognize commands like "*set the bedroom light to red*" and send a `rhasspy_ChangeLightState` to Home Assistant with the following data:

    {
      "name": "bedroom",
      "color": "red"
    }
    
You can now fill in the rest of the Home Assistant automation:
    
    automation:
      # Change the light in the bedroom to red.
      trigger:
        platform: event
        event_type: rhasspy_ChangeLightState
        event_data:
          name: bedroom
          color: red
      action:
        service: light.turn_on
        data:
          rgb_color: [255, 0, 0]
          entity_id: light.bedroom
          
This will handle the specific case of setting the bedroom light to red, but not any other color. You can either add additional automations to handle these, or make use of [automation templating](https://www.home-assistant.io/docs/automation/templating/) to do it all at once.
 

# Client/Server Setup

Contributed by [jaburges](https://community.home-assistant.io/u/jaburges)

* Hardware used:
    * Raspberry Pi 3B w/ 8GB SD card
    * [Seeed 4 Mic Array](https://www.amazon.com/seeed-Studio-ReSpeaker-4-Mic-Raspberry/dp/B076SSR1W1)
* Software used:
    * [Raspbian Buster Lite](https://downloads.raspberrypi.org/raspbian_lite_latest)
    * [Etcher](https://www.balena.io/etcher/)
    * Docker ([install Docker](installation.md#docker))
    
## Server Steps

1. Assuming you already have docker running, create a directory for Rhasspy, and subdirectory called profiles.
2. Pull and Run docker image:

        docker run -p 12101:12101 \
              --restart unless-stopped \
              --name rhasspy \
              -v "/<PATH_TO>/rhasspy/profiles:/profiles" \
              synesthesiam/rhasspy-server:latest \
              --user-profiles /profiles \
              --profile en

3. Goto server URL `http://<Server_IP>:12101` (you may be asked to download files)
4. Goto settings and check config (and save along the way):

        [Rhasspy]
        Listen for wake word on Startup = UNchecked

        [Home Assistant]
        Do not use Home Assistant (note you obviously can instead of Node-Red)

        [Wake Word]
        No Wake word on this device

        [Voice Detection]
        No voice communication on this device

        [Speech Recognition]
        Do Speech recognition with pocketsphinx

        [Intent Recognition]
        Do intent recognition with fuzzywuzzy

        [Text to Speech]
        No Text to speech on this device

        [Audio Recording]
        No recording on this device

        [Audio Playing]
        No Playback on this device

 5. Check Slots, and Sentences tabs and make sure to hit `Train` and then `Restart`

## Client Steps

1. Flash 8Gb MicroSD Card with [Buster](https://downloads.raspberrypi.org/raspbian_lite_latest) with [Etcher](https://www.balena.io/etcher/).
2. Remove and re-insert MicroSD card and add files to the root directory (for headless setup - meaning no screen needed). You only need `wpa_supplicant` if you plan to use WiFi.
    * a file simply called `ssh`
    * `wpa_supplicant.conf` ([example here](https://pastebin.com/cDhyhQLs))
3. Insert the MicroSD card in the Pi, use a proper Power Supply and check your router for the IP address it gets.
4. SSH into the Pi using that IP address (I use [Putty](https://the.earth.li/~sgtatham/putty/latest/w64/putty-64bit-0.73-installer.msi)) using pi default user/pass = pi/raspberry.
   You are going to want to change that in the future!
5. Install git:

        sudo apt install git

6. Install Seeed mic array based on info [here](https://github.com/respeaker/seeed-voicecard) 

        git clone https://github.com/respeaker/seeed-voicecard
        cd seeed-voicecard
        sudo ./install.sh 
        sudo reboot

7. Plug in Seeed speaker and check install was successful against expected result here 5:

        arecord -L

8. Install docker:

        curl -sSL https://get.docker.com | sh

9. Modify user permissions to access docker without using `sudo` all the time ;)

        sudo usermod -a -G docker pi

10. Close SSH, and relaunch SSH connection to use new permissions.
11. Create directories for Rhasspy Docker image to use:

        cd /home/pi
        mkdir rhasspy
        cd rhasspy
        mkdir profiles

12. Pull and run docker image:

        docker run -p 12101:12101 \
              --restart unless-stopped \
              --name rhasspy \
              -v "/home/pi/rhasspy/profiles:/profiles" \
              --device /dev/snd:/dev/snd \
              synesthesiam/rhasspy-server:latest \
              --user-profiles /profiles \
              --profile en

13. Goto Client URL `http://<Pi_IP_address>:12101` (you will be asked to download some files)
    (At time of writing I put Wakeword, voice detection and recognition on the client)
14. Under settings ensure the following is selected, Save along the way. You will need to Train once also.

            [Rhasspy]
            Listen for wake word on Startup = checked

            [Home Assistant]
            Do not use Home Assistant (note you obviously can instead of Node-Red)

            [Wake Word]
            Use snowboy (this should trigger a download of more files)

            [Voice Detection]
            Use webrtcvad and listen for silence

            [Speech Recognition]
            Use Remote Rhasspy server for speech recognition:
            URL = http://<SERVER_IP>:12101/api/speech-to-text

            [Intent Recognition]
            Use Remote Rhasspy server for speech recognition:
            URL = http://<SERVER_IP>:12101/api/text-to-intent

            [Text to Speech]
            No Text to speech on this device

            [Audio Recording]
            Use PyAudio (default)
            Input Device = seeed-4mic-voicecard (you can test this if you want)

            [Audio Playing]
            No Playback on this device

### Node-Red Config

1. Import [this flow](https://github.com/synesthesiam/rhasspy/blob/cda3a02775865d49b52d32a3af7264b7cbd69472/examples/nodered/time-light-flow.js) from the Rhasspy examples
2. Attach a debug node to the websocket in and configure it to show full msg object.
3. I edited light text node to take this:

        {
          "domain": "light",
          "service": "turn_{{slots.state}}",
          "entity_id": "{{slots.name}}"
        }

4. Add a call service node after the light text and leave it blank. Deploy and Enjoy offline voice assistant.

Pick a light (that is a light domain not a switch), and say "Snowboy, turn bedroom light off" :)

