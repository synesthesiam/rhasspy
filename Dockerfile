ARG BUILD_ARCH
FROM synesthesiam/addon-base:$BUILD_ARCH
LABEL maintainer="Michael Hansen <hansen.mike@gmail.com>"

ARG BUILD_ARCH
ENV LANG C.UTF-8

WORKDIR /

RUN apt-get update && \
    apt-get install -y bash python3 python3-dev \
        python3-pip python3-setuptools \
        build-essential portaudio19-dev swig \
        sox espeak alsa-utils \
        openjdk-8-jre-headless \
        cmake git \
        autoconf libtool automake bison \
        sphinxbase-utils sphinxtrain

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
RUN cd / && wget -q https://github.com/synesthesiam/jsgf-gen/releases/download/v1.0/jsgf-gen-1.0_all.deb

# Install phoentisaurus
RUN cd / && wget -q https://github.com/synesthesiam/phonetisaurus-2013/releases/download/v1.0-${BUILD_ARCH}/phonetisaurus_2013-1_${BUILD_ARCH}.deb

# Install opengrm
RUN cd / && wget -q https://github.com/synesthesiam/docker-opengrm/releases/download/v1.3.4-${BUILD_ARCH}/openfst_1.6.9-1_${BUILD_ARCH}.deb
RUN cd / && wget -q https://github.com/synesthesiam/docker-opengrm/releases/download/v1.3.4-${BUILD_ARCH}/opengrm_1.3.4-1_${BUILD_ARCH}.deb

RUN dpkg -i /*.deb

# Copy bw and mllr_solve to /usr/bin
RUN find / -name bw -exec cp '{}' /usr/bin/ \;
RUN find / -name mllr_solve -exec cp '{}' /usr/bin/ \;

RUN ldconfig

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

ENTRYPOINT ["/run.sh"]
