ARG BUILD_FROM
FROM $BUILD_FROM
LABEL maintainer="Michael Hansen <hansen.mike@gmail.com>"

ARG BUILD_ARCH
ARG CPU_ARCH
ENV LANG C.UTF-8

ARG MAKE_THREADS=4

WORKDIR /

COPY etc/qemu-arm-static /usr/bin/
COPY etc/qemu-aarch64-static /usr/bin/

RUN apt-get update && \
    apt-get install -y bash jq unzip \
                       python3 python3-pip python3-dev \
                       build-essential portaudio19-dev swig \
                       libfst-dev libfst-tools \
                       libatlas-base-dev \
                       sox espeak flite alsa-utils \
                       git curl \
                       autoconf libtool automake bison \
                       sphinxbase-utils sphinxtrain

COPY download/phonetisaurus-2019_${BUILD_ARCH}.deb /phonetisaurus.deb
RUN dpkg -i /phonetisaurus.deb && \
    rm /phonetisaurus.deb

# Install Opengrm
COPY download/opengrm-ngram-1.3.3.tar.gz /
RUN cd / && tar -xf opengrm-ngram-1.3.3.tar.gz && \
    cd opengrm-ngram-1.3.3 && \
    ./configure && \
    make -j $MAKE_THREADS && \
    make install && \
    ldconfig && \
    rm -rf /opengrm*

# Install Python dependencies
RUN python3 -m pip install --no-cache-dir wheel

COPY download/jsgf2fst-0.1.0.tar.gz \
     /download/

RUN apt-get install -y libfreetype6-dev libpng-dev pkg-config libffi-dev libssl-dev
COPY requirements.txt /requirements.txt
RUN if [ "$BUILD_ARCH" != "amd64" ]; then \
    grep -v flair /requirements.txt > /requirements-noflair.txt; \
    mv /requirements-noflair.txt /requirements.txt; \
    fi
RUN python3 -m pip install --no-cache-dir -r /requirements.txt

# Install Pocketsphinx Python module with no sound
COPY download/pocketsphinx-python.tar.gz /
RUN python3 -m pip install --no-cache-dir /pocketsphinx-python.tar.gz && \
    rm -rf /pocketsphinx-python*

# Install snowboy
COPY download/snowboy-1.3.0.tar.gz /
RUN if [ "$BUILD_ARCH" != "aarch64" ]; then pip3 install --no-cache-dir /snowboy-1.3.0.tar.gz; fi

# Install Mycroft Precise
COPY download/precise-engine_0.3.0_${CPU_ARCH}.tar.gz /precise-engine.tar.gz
RUN if [ "$BUILD_ARCH" != "aarch64" ]; then \
    cd / && tar -xzf /precise-engine.tar.gz && \
    ln -s /precise-engine/precise-engine /usr/bin/precise-engine && \
    rm /precise-engine.tar.gz; \
    fi

RUN apt-get install -y flite libttspico-utils

COPY download/kaldi_${BUILD_ARCH}.tar.gz /kaldi.tar.gz
RUN mkdir -p /opt && \
    tar -C /opt -xzf /kaldi.tar.gz && \
    rm /kaldi.tar.gz

RUN ldconfig

# Copy bw and mllr_solve to /usr/bin
RUN find / -name bw -exec cp '{}' /usr/bin/ \;
RUN find / -name mllr_solve -exec cp '{}' /usr/bin/ \;

ENV RHASSPY_APP /usr/share/rhasspy

# Copy script to run
COPY docker/run.sh /run.sh
RUN chmod +x /run.sh



COPY profiles/en/ ${RHASSPY_APP}/profiles/en/

COPY profiles/defaults.json ${RHASSPY_APP}/profiles/
COPY docker/rhasspy ${RHASSPY_APP}/bin/
COPY dist/ ${RHASSPY_APP}/dist/
COPY etc/wav/* ${RHASSPY_APP}/etc/wav/
COPY rhasspy/profile_schema.json ${RHASSPY_APP}/rhasspy/
COPY *.py ${RHASSPY_APP}/
COPY rhasspy/*.py ${RHASSPY_APP}/rhasspy/

ENV CONFIG_PATH /data/options.json

ENTRYPOINT ["/run.sh"]