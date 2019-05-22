SHELL := bash
.PHONY: docker deb

BUILD_FROM ?= ubuntu:bionic
BUILD_ARCH ?= amd64
FRIENDLY_ARCH ?= amd64
DOCKER_TAG := rhasspy-tools-build:${FRIENDLY_ARCH}

# Expecting in download/
# openfst-1.6.2.tar.gz
# opengrm-ngram-1.3.3.tar.gz
# phonetisaurus-2019.tar.gz
# python-openfst-1.6.1.tar.gz

all:
	docker build -f Dockerfile \
        --build-arg BUILD_FROM=${BUILD_ARCH}/${BUILD_FROM} \
        -t ${DOCKER_TAG} .
	docker run -i ${DOCKER_TAG} \
        tar -C /build -czf - . > \
        dist/rhasspy-tools_${FRIENDLY_ARCH}.tar.gz

test:
	rm -rf test-venv
	python3 -m venv test-venv
	tar -C test-venv -xf dist/rhasspy-tools_${FRIENDLY_ARCH}.tar.gz
	source test-venv/bin/activate && \
        pip3 install wheel && \
        pip3 install download/python-openfst-1.6.1.tar.gz && \
        python3 -c 'import pywrapfst'
