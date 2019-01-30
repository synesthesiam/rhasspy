ARG BUILD_ARCH
FROM synesthesiam/addon-base:$BUILD_ARCH
LABEL maintainer="Michael Hansen <hansen.mike@gmail.com>"

ARG BUILD_ARCH
ENV LANG C.UTF-8

ARG MAKE_THREADS=4

WORKDIR /

RUN apt-get update && \
    apt-get install -y bash \
        build-essential portaudio19-dev swig \
        libatlas-base-dev \
        sox espeak alsa-utils \
        openjdk-8-jre-headless \
        cmake git \
        autoconf libtool automake bison \
        sphinxbase-utils sphinxtrain

# Install opengrm (with openfst 1.6.9)
COPY etc/openfst-1.6.9.tar.gz /
RUN cd / && tar -xf openfst-1.6.9.tar.gz && cd openfst-1.6.9/ && \
    ./configure --enable-far && \
    make -j $MAKE_THREADS && \
    make install && \
    rm -rf /openfst-1.6.9*

COPY etc/opengrm-ngram-1.3.4.tar.gz /
RUN cd / && tar -xf opengrm-ngram-1.3.4.tar.gz && cd opengrm-ngram-1.3.4/ && \
    ./configure && \
    make -j $MAKE_THREADS && \
    make install && \
    rm -rf /opengrm*

# Install phonetisaurus (with openfst 1.3.4)
COPY etc/openfst-1.3.4.tar.gz /
RUN cd / && tar -xvf openfst-1.3.4.tar.gz && \
    cd /openfst-1.3.4/ && \
    ./configure --enable-compact-fsts --enable-const-fsts \
                --enable-far --enable-lookahead-fsts \
                --enable-pdt && \
    make -j $MAKE_THREADS

COPY etc/phonetisaurus-2013.tar.gz /
RUN cd / && tar -xvf phonetisaurus-2013.tar.gz && \
    cd /phonetisaurus-2013/src && \
    mkdir -p bin && \
    CPPFLAGS=-I/openfst-1.3.4/src/include LDFLAGS=-L/openfst-1.3.4/src/lib/.libs/ make -j $MAKE_THREADS bin/phonetisaurus-g2p && \
    cp bin/phonetisaurus-g2p /usr/bin/ && \
    cp /openfst-1.3.4/src/lib/.libs/libfst.* /usr/local/lib/ && \
    rm -rf /openfst-1.3.4* && \
    rm -rf /phonetisaurus-2013*

# Install Python dependencies
COPY requirements.txt /requirements.txt
RUN python3 -m pip install --no-cache-dir wheel
RUN python3 -m pip install --no-cache-dir -r /requirements.txt

# Install Pocketsphinx Python module with no sound
COPY etc/pocketsphinx-python.tar.gz /
RUN python3 -m pip install --no-cache-dir /pocketsphinx-python.tar.gz && \
    rm -rf /pocketsphinx-python*

# Install JSGF sentence generator
COPY etc/jsgf-gen.tar.gz /
RUN cd / && tar -xvf /jsgf-gen.tar.gz && \
    mv /jsgf-gen/bin/* /usr/bin/ && \
    mv /jsgf-gen/lib/* /usr/lib/ && \
    rm -rf /jsgf-gen*

# Install snowboy
COPY etc/snowboy-1.3.0.tar.gz /
RUN pip3 install --no-cache-dir /snowboy-1.3.0.tar.gz && \
    rm -rf /snowboy*

RUN ldconfig

# Copy my code
COPY *.py /usr/share/rhasspy/
COPY rhasspy/*.py /usr/share/rhasspy/rhasspy/
COPY profiles/ /usr/share/rhasspy/profiles/
COPY dist/ /usr/share/rhasspy/dist/

# Copy bw and mllr_solve to /usr/bin
RUN find / -name bw -exec cp '{}' /usr/bin/ \;
RUN find / -name mllr_solve -exec cp '{}' /usr/bin/ \;

# Copy script to run
COPY docker/run.sh /run.sh
RUN chmod a+x /run.sh

ENV CONFIG_PATH /data/options.json

CMD ["/run.sh"]
