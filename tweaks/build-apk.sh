#!/bin/sh
# Build the nura-g8x-tweaks apk in an official Alpine edge container (arm64).
# Usage: sh tweaks/build-apk.sh   ->  out/apk/aarch64/nura-g8x-tweaks-*.apk
set -e
cd "$(dirname "$0")/.."
A=pmaports/device/testing/nura-g8x-tweaks
# reproducible files tarball from unit/ and tweaks/
docker run --rm -v "$PWD":/n -w /n alpine:3.22 sh -c '
	apk add -q tar gzip >/dev/null
	T=$(mktemp -d); mkdir -p $T/files
	cp -r unit tweaks $T/files/
	find $T/files -name __pycache__ -prune -exec rm -rf {} +
	find $T/files -name "._*" -delete
	tar --sort=name --mtime=2026-01-01 --owner=0 --group=0 --numeric-owner \
		-C $T -cf - files | gzip -n > '$A'/nura-g8x-tweaks-files.tar.gz'
mkdir -p out/apk
docker run --rm -v "$PWD":/n alpine:edge sh -c '
	set -e
	apk add -q alpine-sdk sudo >/dev/null
	adduser -D b; addgroup b abuild; echo "b ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/b
	mkdir -p /home/b/a; cp -r /n/'$A'/. /home/b/a/; chown -R b /home/b
	# persistent signing key (private, never published): out/apk-key/
	mkdir -p /n/out/apk-key /home/b/.config/abuild; chown -R b /home/b
	if ! ls /n/out/apk-key/*.rsa >/dev/null 2>&1; then
		su b -c "abuild-keygen -an -b 4096" >/dev/null
		cp /home/b/.config/abuild/*.rsa /home/b/.config/abuild/*.rsa.pub /n/out/apk-key/
	fi
	cp /n/out/apk-key/* /home/b/.config/abuild/; chown -R b /home/b/.config/abuild
	echo "PACKAGER_PRIVKEY=\"$(ls /home/b/.config/abuild/*.rsa)\"" > /home/b/.config/abuild/abuild.conf
	cp /home/b/.config/abuild/*.rsa.pub /etc/apk/keys/
	su b -c "cd /home/b/a && abuild checksum && abuild -r -P /home/b/pkgs"
	cp /home/b/a/APKBUILD /n/'$A'/APKBUILD
	cp -r /home/b/pkgs/* /n/out/apk/'
ls -l out/apk/*/
