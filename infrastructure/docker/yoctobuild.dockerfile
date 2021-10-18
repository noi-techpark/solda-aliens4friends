FROM registry.ostc-eu.org/ostc/containers/ostc-builder:latest

# Information: https://git.ostc-eu.org/OSTC/containers/-/tree/main/ostc-builder
# Run docker inspect to get org.opencontainers.image.documentation:
# Based on: https://git.ostc-eu.org/OSTC/containers/-/blob/main/ostc-builder/Dockerfile

USER root

COPY --chown=ostc-builder:ostc-builder infrastructure/utils/yoctobuilder.py /usr/local/bin/yoctobuilder
RUN chmod +x /usr/local/bin/yoctobuilder

ARG DEBIAN_FRONTEND=noninteractive
RUN	apt-get update && \
	apt-get install -y python3-yaml rsync rpm && \
	apt-get install -y 'ca-certificates=20210119~20.04.2' && \
	apt-get autoremove --purge -y && apt-get clean && rm -rf /var/lib/apt/lists/*

ARG GIT_REF=HEAD
RUN wget -qO /usr/local/bin/aliensrc_creator https://git.ostc-eu.org/oss-compliance/toolchain/tinfoilhat/-/raw/${GIT_REF}/aliensrc_creator.py && \
    wget -qO /usr/local/bin/tinfoilhat https://git.ostc-eu.org/oss-compliance/toolchain/tinfoilhat/-/raw/${GIT_REF}/tinfoilhat.py && \
	chmod +x /usr/local/bin/aliensrc_creator /usr/local/bin/tinfoilhat

USER ostc-builder
CMD [ "bash" ]
