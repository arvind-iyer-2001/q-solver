# Reference Dockerfile — not used directly at runtime.
# docker_manager.py builds the image from memory with the license key substituted.
# To build manually:
#   docker build --build-arg LICENSE_KEY=<your_b64_license> -t q-solver:latest docker/
FROM ubuntu:22.04
ARG LICENSE_KEY
ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
RUN apt-get update && apt-get install -y curl unzip ncurses-bin && \
    curl -sLO https://portal.dl.kx.com/assets/raw/kdb-x/install_kdb/~latest~/install_kdb.sh && \
    bash install_kdb.sh -y --b64lic ${LICENSE_KEY}
