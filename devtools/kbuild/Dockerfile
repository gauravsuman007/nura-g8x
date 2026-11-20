# Kernel build environment for the LG G8x (Nura). Sources, build output and ccache live on the
# case-sensitive volume /Volumes/NuraBuild (mounted at /b); this image only holds the toolchain.
FROM alpine:3.22
RUN apk add --no-cache build-base clang lld llvm bison flex elfutils-dev openssl-dev perl python3 \
        linux-headers findutils bash tar gzip dtc pahole xz diffutils ccache git patch rsync
ENV CCACHE_DIR=/b/ccache CCACHE_MAXSIZE=30G CCACHE_COMPILERCHECK=content CCACHE_BASEDIR=/b
WORKDIR /b
