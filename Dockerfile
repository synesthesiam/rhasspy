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

# Install Python dependencies
COPY requirements.txt /requirements.txt
COPY etc/nanomsg-python-master.zip /
RUN python3 -m pip install --no-cache-dir wheel
RUN python3 -m pip install --no-cache-dir -r /requirements.txt

# Install Pocketsphinx Python module with no sound
COPY etc/pocketsphinx-python.tar.gz /
RUN python3 -m pip install --no-cache-dir /pocketsphinx-python.tar.gz

# Install JSGF sentence generator
COPY etc/jsgf-gen.tar.gz /
RUN cd / && tar -xvf /jsgf-gen.tar.gz && mv /jsgf-gen/* /usr/

# Install phoentisaurus
COPY etc/phonetisaurus-2013.tar.gz /
RUN cd / && wget -q https://github.com/synesthesiam/phonetisaurus-2013/releases/download/v1.0-${BUILD_ARCH}/phonetisaurus_2013-1_${BUILD_ARCH}.deb

#RUN apk update && \
#    apk add git build-base && \
#    cd / && git clone https://github.com/synesthesiam/openfst-1.3.4.git && \
#    cd /openfst-1.3.4/ && \
#    ./configure --enable-compact-fsts --enable-const-fsts --enable-far --enable-lookahead-fsts --enable-pdt --enable-static --disable-shared && \
#    make -j $MAKE_THREADS && \
#    cd /phonetisaurus-2013/src && \
#    mkdir -p bin && \
#    CPPFLAGS=-I/openfst-1.3.4/src/include LDFLAGS=-L/openfst-1.3.4/src/lib/.libs make -j $MAKE_THREADS bin/phonetisaurus-g2p && \
#    cp bin/phonetisaurus-g2p /usr/bin && \
#    rm -rf /openfst* /phonetisaurus* && \
#    apk del git build-base && \
#    apk add libstdc++

# Install opengrm
RUN cd / && wget -q https://github.com/synesthesiam/docker-opengrm/releases/download/v1.3.4-${BUILD_ARCH}/openfst_1.6.9-1_${BUILD_ARCH}.deb
RUN cd / && wget -q https://github.com/synesthesiam/docker-opengrm/releases/download/v1.3.4-${BUILD_ARCH}/opengrm_1.3.4-1_${BUILD_ARCH}.deb

RUN dpkg -i /*.deb && rm -f /*.deb

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
