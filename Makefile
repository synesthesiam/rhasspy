.PHONY: web-dist docker demo release client server alpine
SHELL := bash
BUILD_ARCH ?= amd64
RELEASE_FILES := Dockerfile \
                 *.py \
                 build.json \
                 config.json \
                 requirements.txt \
                 bin/install-profiles.sh \
                 dist/ \
                 docker/run.sh \
                 profiles/defaults.json

LANGUAGES := de en es fr it nl ru
RASA_LANGUAGES := de en es fr it nl

docker:
	docker build . \
    --build-arg BUILD_FROM=homeassistant/${BUILD_ARCH}-base:latest \
    --build-arg BUILD_ARCH=${BUILD_ARCH} \
    -t synesthesiam/rhasspy-hassio-addon:${BUILD_ARCH}

demo:
	docker build . \
    -f Dockerfile.demo \
    --build-arg BUILD_ARCH=${BUILD_ARCH} \
    -t synesthesiam/rhasspy-demo:${BUILD_ARCH}

client:
	docker build . \
    -f Dockerfile.client \
    --build-arg BUILD_ARCH=${BUILD_ARCH} \
    --build-arg LANGUAGES="${LANGUAGES}" \
    -t synesthesiam/rhasspy-client:${BUILD_ARCH}

server:
	docker build . \
    -f Dockerfile.server \
    --build-arg BUILD_ARCH=${BUILD_ARCH} \
    --build-arg LANGUAGES="${RASA_LANGUAGES}" \
    -t synesthesiam/rhasspy-server:${BUILD_ARCH}

alpine:
	docker build . \
    -f Dockerfile.alpine \
    --build-arg BUILD_FROM=homeassistant/${BUILD_ARCH}-base:latest \
    --build-arg BUILD_ARCH=${BUILD_ARCH} \
    --build-arg LANGUAGES="${LANGUAGES}" \
    -t synesthesiam/rhasspy-alpine:${BUILD_ARCH}

web-dist:
	yarn build

release:
	tar -czf rhasspy-hassio-addon.tar.gz ${RELEASE_FILES}
