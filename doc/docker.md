Rhasspy Docker Images
==========================

There are currently two pre-built Rhasspy Docker images [on DockerHub](https://hub.docker.com/u/synesthesiam/) for **amd64** labeled "server" and "client".

Client
-------

The client build of Rhasspy is fully functional, but does not include rasaNLU or spaCy language models. This makes its intent recognition less powerful, but also makes the Docker image half the size!

    docker run -d --name rhasspy-client \
          -p 12101:12101 \
          -e RHASSPY_PROFILES=/profiles \
          -v $HOME/.rhasspy/profiles:/profiles \
          --device /dev/snd:/dev/snd \
          --privileged \
          synesthesiam/rhasspy-client:amd64
          
Now visit http://localhost:12101 for the web interface. Any changes you make to your profile should show up in `$HOME/.rhasspy`. Depending on how you have your sound system set up, Rhasspy should have access to your microphone.

Server
-------

The server build of Rhasspy includes rasaNLU and all spaCy language models. If you have the disk space and processing power, go with this image.

    docker run -d --name rhasspy-server \
          -p 12101:12101 \
          -e RHASSPY_PROFILES=/profiles \
          -v $HOME/.rhasspy/profiles:/profiles \
          --device /dev/snd:/dev/snd \
          --privileged \
          synesthesiam/rhasspy-server:amd64
          
Now visit http://localhost:12101 for the web interface. Any changes you make to your profile should show up in `$HOME/.rhasspy`. Depending on how you have your sound system set up, Rhasspy should have access to your microphone.
