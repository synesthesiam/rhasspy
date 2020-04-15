.PHONY: web-dist docker manifest docs-uml g2p check
SHELL := bash

DOCKER_PLATFORMS = linux/amd64,linux/arm64,linux/arm/v7

all: docker

# -----------------------------------------------------------------------------
# Docker
# -----------------------------------------------------------------------------

docker: web-dist
	docker buildx build . \
        --platform $(DOCKER_PLATFORMS) \
        --tag synesthesiam/rhasspy-server:latest \
        --push

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

check:
	flake8 --exclude=lexconvert.py app.py test.py rhasspy/*.py
	pylint --ignore=lexconvert.py app.py test.py rhasspy/*.py
	mypy app.py test.py rhasspy/*.py
