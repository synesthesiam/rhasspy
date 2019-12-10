.PHONY: web-dist docker manifest docs-uml g2p check
SHELL := bash

# -----------------------------------------------------------------------------
# Docker
# -----------------------------------------------------------------------------

docker: web-dist docker-amd64 docker-armhf docker-aarch64 docker-push manifest

docker-amd64:
	docker build . -f docker/templates/dockerfiles/Dockerfile.prebuilt.alsa.all \
    --build-arg BUILD_ARCH=amd64 \
    --build-arg CPU_ARCH=x86_64 \
    --build-arg BUILD_FROM=ubuntu:bionic \
    -t synesthesiam/rhasspy-server:amd64

docker-armhf:
	docker build . -f docker/templates/dockerfiles/Dockerfile.prebuilt.alsa.all \
     --build-arg BUILD_ARCH=armhf \
     --build-arg CPU_ARCH=armv7l \
     --build-arg BUILD_FROM=arm32v7/ubuntu:bionic \
     -t synesthesiam/rhasspy-server:armhf

docker-aarch64:
	docker build . -f docker/templates/dockerfiles/Dockerfile.prebuilt.alsa.all \
     --build-arg BUILD_ARCH=aarch64 \
     --build-arg CPU_ARCH=arm64v8 \
     --build-arg BUILD_FROM=arm64v8/ubuntu:bionic \
     -t synesthesiam/rhasspy-server:aarch64

docker-push:
	docker push synesthesiam/rhasspy-server:amd64
	docker push synesthesiam/rhasspy-server:armhf
	docker push synesthesiam/rhasspy-server:aarch64

manifest:
	docker manifest push --purge synesthesiam/rhasspy-server:latest
	docker manifest create --amend synesthesiam/rhasspy-server:latest \
        synesthesiam/rhasspy-server:amd64 \
        synesthesiam/rhasspy-server:armhf \
        synesthesiam/rhasspy-server:aarch64
	docker manifest annotate synesthesiam/rhasspy-server:latest synesthesiam/rhasspy-server:armhf --os linux --arch arm
	docker manifest annotate synesthesiam/rhasspy-server:latest synesthesiam/rhasspy-server:aarch64 --os linux --arch arm64
	docker manifest push synesthesiam/rhasspy-server:latest

# -----------------------------------------------------------------------------
# Yarn (Vue)
# -----------------------------------------------------------------------------

web-dist:
	yarn build
	mkdir -p download
	rm -f download/rhasspy-web-dist.tar.gz
	tar -czf download/rhasspy-web-dist.tar.gz dist/

# -----------------------------------------------------------------------------
# Documentation
# -----------------------------------------------------------------------------

DOCS_UML_FILES := $(wildcard docs/img/*.uml.txt)
DOCS_PNG_FILES := $(patsubst %.uml.txt,%.png,$(DOCS_UML_FILES))

%.png: %.uml.txt
	plantuml -p -tsvg < $< | inkscape --export-dpi=300 --export-png=$@ /dev/stdin

docs-uml: $(DOCS_PNG_FILES)

# -----------------------------------------------------------------------------
# Grapheme-to-Phoneme
# -----------------------------------------------------------------------------

G2P_LANGUAGES := de en es fr it nl ru
G2P_MODELS := $(foreach lang,$(G2P_LANGUAGES),profiles/$(lang)/g2p.fst)

g2p: $(G2P_MODELS)

%/g2p.fst: %/base_dictionary.txt
	./make-g2p.sh $< $@

# -----------------------------------------------------------------------------
# Testing
# -----------------------------------------------------------------------------

mypy:
	mypy app.py rhasspy

check:
	flake8 --exclude=lexconvert.py app.py test.py rhasspy/*.py
	pylint --ignore=lexconvert.py app.py test.py rhasspy/*.py
