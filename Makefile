.PHONY: web-dist docker demo release
SHELL := bash
BUILD_ARCH ?= amd64
RELEASE_FILES := Dockerfile \
                 *.py \
                 config.json \
                 requirements.txt \
                 dist/ \
                 docker/run.sh \
                 profiles/defaults.json \
                 profiles/en/acoustic_model/ \
                 profiles/en/*.json \
                 profiles/en/*.txt \
                 profiles/en/*.ini \
                 profiles/en/g2p.fst

docker:
	docker build . \
    --build-arg BUILD_FROM=homeassistant/${BUILD_ARCH}-base:latest \
    --build-arg BUILD_ARCH=${BUILD_ARCH} \
    -t synesthesiam/rhasspy-hassio-addon:${BUILD_ARCH}

demo:
	docker build . \
    -f Dockerfile.demo \
    --build-arg BUILD_ARCH=${BUILD_ARCH} \
    -t synesthesiam/rhasspy-demo:${BUILD_ARCH} --no-cache

web-dist:
	yarn build

release:
	tar -czf rhasspy-hassio-addon.tar.gz ${RELEASE_FILES}
