FROM ubuntu:22.04 AS builder
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y curl unzip ncurses-bin && rm -rf /var/lib/apt/lists/*
RUN curl -sLO https://portal.dl.kx.com/assets/raw/kdb-x/install_kdb/~latest~/install_kdb.sh &&     bash install_kdb.sh -y --b64lic '***REMOVED***' &&     rm install_kdb.sh

FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y ncurses-bin && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.kx/bin /root/.kx/bin
COPY --from=builder /root/.kx/mod /root/.kx/mod
