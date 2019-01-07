ARG BUILD_FROM
FROM $BUILD_FROM

ARG BUILD_ARCH
ARG LANGUAGES="de en es fr it nl ru"
LABEL maintainer="Michael Hansen <hansen.mike@gmail.com>"

ENV LANG C.UTF-8

WORKDIR /

RUN apk update && \
    apk add --no-cache bash python3 python3-dev \
        build-base portaudio-dev swig \
        sox espeak alsa-utils \
        openjdk8-jre \
        cmake git \
        autoconf libtool automake bison

# Install nanomsg from source (no armhf alpine package currently available).
# Also need to copy stuff in /usr to avoid a call to ldconfig, which fails
# for some reason.
COPY etc/nanomsg-1.1.5.tar.gz /
RUN tar -xzf /nanomsg-1.1.5.tar.gz && \
    cd /nanomsg-1.1.5 && \
    mkdir build && \
    cd build && \
    cmake .. && \
    cmake --build . && \
    cmake --build . --target install && \
    cp -R /usr/local/include/nanomsg /usr/include/ && \
    find /usr/local -name 'libnanomsg.so*' -exec cp {} /usr/lib/ \; && \
    rm -rf /nanomsg-1.1.5*

# Install Python dependencies
COPY requirements.txt /requirements.txt
COPY etc/nanomsg-python-master.zip /
RUN python3 -m pip install --no-cache-dir wheel
RUN python3 -m pip install --no-cache-dir -r /requirements.txt
RUN python3 -m pip install --no-cache-dir /nanomsg-python-master.zip

# Install Pocketsphinx Python module with no sound
RUN python3 -m pip install https://github.com/synesthesiam/pocketsphinx-python/releases/download/v1.0/pocketsphinx-python.tar.gz

# Install JSGF sentence generator
RUN cd / && wget -qO - https://github.com/synesthesiam/jsgf-gen/releases/download/v1.0/jsgf-gen.tar.gz | tar xzf - && \
    ln -s /jsgf-gen/bin/jsgf-gen /usr/bin/jsgf-gen

# Install phoentisaurus
RUN cd / && wget -qO - https://github.com/synesthesiam/phonetisaurus-2013/releases/download/v1.0-$BUILD_ARCH-alpine/phonetisaurus_2013-1_$BUILD_ARCH-alpine.tar.gz | tar xzf -

# Install opengrm
RUN cd / && wget -qO - https://github.com/synesthesiam/docker-opengrm/releases/download/v1.3.4-$BUILD_ARCH-alpine/opengrm-1.3.4_$BUILD_ARCH-alpine.tar.gz | tar xzf -

# Install sphinxbase
RUN cd / && git clone https://github.com/cmusphinx/sphinxbase.git && \
    cd sphinxbase && \
    ./autogen.sh && \
    make && \
    make install && \
    rm -rf /sphinxbase*

RUN cd / && git clone https://github.com/cmusphinx/sphinxtrain.git && \
    cd sphinxtrain && \
    ./autogen.sh && \
    make && \
    make install && \
    rm -rf /sphinxtrain*

# Copy bw and mllr_solve to /usr/bin
RUN find / -name bw -exec cp '{}' /usr/bin/ \;
RUN find / -name mllr_solve -exec cp '{}' /usr/bin/ \;

# Install Rhasspy profiles
COPY bin/install-profiles.sh /
RUN mkdir -p /usr/share/rhasspy/profiles && \
    cd /usr/share/rhasspy/profiles && \
    bash /install-profiles.sh $LANGUAGES

# Copy my code
COPY *.py /usr/share/rhasspy/
COPY rhasspy/ /usr/share/rhasspy/
COPY profiles/ /usr/share/rhasspy/profiles/
COPY dist/ /usr/share/rhasspy/dist/
COPY etc/wav/ /usr/share/rhasspy/etc/wav/
COPY docker/rhasspy /usr/share/rhasspy/bin/

# Copy script to run
COPY docker/run.sh /run.sh
RUN chmod a+x /run.sh

ENV CONFIG_PATH /data/options.json

CMD ["/run.sh"]
