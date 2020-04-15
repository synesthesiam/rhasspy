FROM ubuntu:eoan as build
ARG TARGETPLATFORM
ARG TARGETARCH
ARG TARGETVARIANT

ENV LANG C.UTF-8
ENV RHASSPY_APP /usr/share/rhasspy
ENV RHASSPY_VENV ${RHASSPY_APP}/.venv

WORKDIR /

RUN apt-get update && \
    apt-get install --no-install-recommends --yes \
        python3 python3-dev python3-setuptools python3-pip python3-venv \
        build-essential swig portaudio19-dev libatlas-base-dev

COPY etc/shflags ${RHASSPY_APP}/etc/
COPY download/rhasspy-tools_*.tar.gz \
     download/kaldi_*.tar.gz \
     download/pocketsphinx-python.tar.gz \
     download/snowboy-1.3.0.tar.gz \
     download/precise-engine_0.3.0_*.tar.gz \
     ${RHASSPY_APP}/download/
COPY create-venv.sh download-dependencies.sh requirements.txt ${RHASSPY_APP}/
RUN cd ${RHASSPY_APP} && ./create-venv.sh --nosystem --noweb

# -----------------------------------------------------------------------------

FROM ubuntu:eoan
ARG TARGETPLATFORM
ARG TARGETARCH
ARG TARGETVARIANT

ENV LANG C.UTF-8
ENV RHASSPY_APP /usr/share/rhasspy
ENV RHASSPY_VENV ${RHASSPY_APP}/.venv

WORKDIR /

COPY --from=build ${RHASSPY_VENV} ${RHASSPY_VENV}
COPY --from=build ${RHASSPY_APP}/opt/kaldi/ ${RHASSPY_APP}/opt/kaldi/

RUN apt-get update && \
    apt-get install --no-install-recommends --yes \
        python3 python3-dev \
        bash jq unzip curl perl \
        libportaudio2 libatlas3-base \
        libgfortran4 ca-certificates \
        sox espeak flite libttspico-utils alsa-utils lame \
        libasound2-plugins \
        libfreetype6-dev libpng-dev pkg-config libffi-dev libssl-dev \
        gstreamer1.0-tools gstreamer1.0-plugins-good

# Web interface
ADD download/rhasspy-web-dist.tar.gz ${RHASSPY_APP}/

RUN ldconfig

# Copy script to run
COPY docker/run.sh /run.sh
RUN chmod +x /run.sh

COPY profiles/ ${RHASSPY_APP}/profiles/

COPY profiles/defaults.json ${RHASSPY_APP}/profiles/
COPY docker/rhasspy ${RHASSPY_APP}/bin/
COPY dist/ ${RHASSPY_APP}/dist/
COPY etc/wav/* ${RHASSPY_APP}/etc/wav/
COPY rhasspy/profile_schema.json ${RHASSPY_APP}/rhasspy/
COPY rhasspy/train/jsgf2fst/*.py ${RHASSPY_APP}/rhasspy/train/jsgf2fst/
COPY rhasspy/train/*.py ${RHASSPY_APP}/rhasspy/train/
COPY *.py ${RHASSPY_APP}/
COPY rhasspy/*.py ${RHASSPY_APP}/rhasspy/
COPY VERSION ${RHASSPY_APP}/

ENV CONFIG_PATH /data/options.json
ENV KALDI_PREFIX ${RHASSPY_APP}/opt

ENTRYPOINT ["/run.sh"]
