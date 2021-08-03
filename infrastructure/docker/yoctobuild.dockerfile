FROM registry.ostc-eu.org/ostc/containers/ostc-builder:latest

# Information: https://git.ostc-eu.org/OSTC/containers/-/tree/main/ostc-builder
# Run docker inspect to get org.opencontainers.image.documentation:
# Based on: https://git.ostc-eu.org/OSTC/containers/-/blob/main/ostc-builder/Dockerfile

USER root

COPY --chown=ostc-builder:ostc-builder infrastructure/utils/yoctobuilder.py /usr/local/bin/yoctobuilder
RUN chmod +x /usr/local/bin/yoctobuilder

RUN wget -qO /usr/local/bin/aliensrc_creator https://git.ostc-eu.org/oss-compliance/toolchain/tinfoilhat/-/raw/master/aliensrc_creator.py && \
    wget -qO /usr/local/bin/tinfoilhat https://git.ostc-eu.org/oss-compliance/toolchain/tinfoilhat/-/raw/master/tinfoilhat.py && \
	chmod +x /usr/local/bin/aliensrc_creator /usr/local/bin/tinfoilhat && \
	DEBIAN_FRONTEND=noninteractive apt-get update && \
	DEBIAN_FRONTEND=noninteractive apt-get install -y python3-yaml rsync rpm && \
	DEBIAN_FRONTEND=noninteractive apt-get autoremove --purge -y

USER ostc-builder
CMD [ "bash" ]
