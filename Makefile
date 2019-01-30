.PHONY: web-dist docker release update-addon manifest
SHELL := bash
RELEASE_FILES := Dockerfile \
                 *.py \
                 requirements.txt \
                 bin/install-profiles.sh \
                 bin/rhasspy \
                 rhasspy/ \
                 dist/ \
                 docker/run.sh \
                 docker/rhasspy \
                 profiles/defaults.json \
                 etc/wav/

ADDON_DIR := ../hassio-addons/rhasspy

docker: docker-amd64 docker-armhf docker-aarch64

docker-amd64:
	docker build . \
    --build-arg BUILD_ARCH=amd64 \
    -t synesthesiam/rhasspy-server:amd64

docker-armhf:
	docker build . \
     --build-arg BUILD_ARCH=armhf \
     -t synesthesiam/rhasspy-server:armhf

docker-aarch64:
	docker build . \
     --build-arg BUILD_ARCH=aarch64 \
     -t synesthesiam/rhasspy-server:aarch64

web-dist:
	yarn build

release:
	tar -czf rhasspy-hassio-addon.tar.gz ${RELEASE_FILES}

update-addon:
	rm -rf ${ADDON_DIR}/dist
	cp Dockerfile *.py requirements.txt ${ADDON_DIR}/
	cp bin/install-profiles.sh ${ADDON_DIR}/bin/
	cp -R rhasspy/ ${ADDON_DIR}/
	cp -R dist/ ${ADDON_DIR}/
	cp -R etc/wav/ ${ADDON_DIR}/etc/
	cp docker/run.sh docker/rhasspy ${ADDON_DIR}/docker/
	cp profiles/defaults.json ${ADDON_DIR}/profiles/

manifest:
	docker manifest push --purge synesthesiam/rhasspy-server:latest
	docker manifest create --amend synesthesiam/rhasspy-server:latest \
        synesthesiam/rhasspy-server:amd64 \
        synesthesiam/rhasspy-server:armhf \
        synesthesiam/rhasspy-server:aarch64
	docker manifest annotate synesthesiam/rhasspy-server:latest synesthesiam/rhasspy-server:armhf --os linux --arch arm
	docker manifest annotate synesthesiam/rhasspy-server:latest synesthesiam/rhasspy-server:aarch64 --os linux --arch arm64
	docker manifest push synesthesiam/rhasspy-server:latest
