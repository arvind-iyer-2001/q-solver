FROM ubuntu:22.04 AS builder
ARG TARGETARCH
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y curl unzip && rm -rf /var/lib/apt/lists/*
RUN case "${TARGETARCH}" in \
        amd64) PREFIX=l64 ;; \
        arm64) PREFIX=l64arm ;; \
        *) echo "unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1 ;; \
    esac && \
    curl -sLf -o kdb.zip "https://portal.dl.kx.com/assets/raw/kdb-x/kdb-x/~latest~/${PREFIX}.zip" && \
    mkdir -p /root/.kx/bin /root/.kx/mod/kx && \
    unzip -p kdb.zip "${PREFIX}/q" > /root/.kx/bin/q && \
    chmod +x /root/.kx/bin/q && \
    rm kdb.zip

FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y ncurses-bin && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.kx/bin /root/.kx/bin
COPY --from=builder /root/.kx/mod /root/.kx/mod
