#!/bin/bash

set -e

tmprepo=$(mktemp -d)

cd $tmprepo
git clone https://git.ostc-eu.org/OSTC/OHOS/manifest
cd manifest
release=$(git describe --tags --always)

mkdir -p /build/allscenarios/$release
cd /build/allscenarios/$release

repo init -u https://git.ostc-eu.org/OSTC/OHOS/manifest.git -b develop
repo sync


FLAVOUR=linux
MACHINES=(qemux86-64 qemux86 seco-intel-b68 stm32mp1-av96 seco-imx8mm-c61 raspberrypi4-64)
IMAGES=(allscenarios-image-base allscenarios-image-base-tests allscenarios-image-extra allscenarios-image-extra-tests)

for m in ${MACHINES[@]}; do
  TEMPLATECONF=../sources/meta-ohos/flavours/$FLAVOUR . ./sources/poky/oe-init-build-env $FLAVOUR-$m
  sed -i.bak -E "s/#MACHINE \?= \"$m\"/MACHINE \?= \"$m\"/" conf/local.conf
  case $m in
    seco-intel-b68)
      echo "CONFIG_SERIAL_OF_PLATFORM= \"y\"" >> conf/local.conf
      ;;
    seco-imx8mm-c61)
      echo "ACCEPT_FSL_EULA = \"1\"" >> conf/local.conf
      ;;
  esac
  # do not use cache
  sed -i \
     -e 's/^INHERIT += "own-mirrors"/#INHERIT \+= "own-mirrors"/' \
     -e 's/^SOURCE_MIRROR_URL/#SOURCE_MIRROR_URL/' \
     -e 's/^SSTATE_MIRRORS/#SSTATE_MIRRORS/' \
     -e 's/^\#SSTATE_DIR ?= .*/SSTATE_DIR ?= "\/build\/common\/sstate-cache"/' \
     -e 's/^\#DL_DIR ?= .*/DL_DIR ?= "\/build\/common\/downloads"/' \
     conf/local.conf
  echo "INHERIT += \"cve-check\"" >> conf/local.conf
  for image in ${IMAGES[@]}; do
    bitbake $image
  done
  cd ..
done

FLAVOUR=zephyr
MACHINES=(qemu-x86 qemu-cortex-m3 96b-nitrogen 96b-avenger96 nrf52840dk-nrf52840 arduino-nano-33-ble)
image=zephyr-philosophers

for m in ${MACHINES[@]}; do
  TEMPLATECONF=../sources/meta-ohos/flavours/$FLAVOUR . ./sources/poky/oe-init-build-env $FLAVOUR-$m
  sed -i.bak -E "s/#MACHINE \?= \"$m\"/MACHINE \?= \"$m\"/" conf/local.conf
    # do not use cache
  sed -i \
     -e 's/^INHERIT += "own-mirrors"/#INHERIT \+= "own-mirrors"/' \
     -e 's/^SOURCE_MIRROR_URL/#SOURCE_MIRROR_URL/' \
     -e 's/^SSTATE_MIRRORS/#SSTATE_MIRRORS/' \
     -e 's/^\#SSTATE_DIR ?= .*/SSTATE_DIR ?= "\/build\/common\/sstate-cache"/' \
     -e 's/^\#DL_DIR ?= .*/DL_DIR ?= "\/build\/common\/downloads"/' \
     conf/local.conf
  echo "INHERIT += \"cve-check\"" >> conf/local.conf
  bitbake $image
  cd ..
done

TEMPLATECONF=../sources/meta-ohos/flavours/freertos . ./sources/poky/oe-init-build-env freertos-qemuarmv5
# do not use cache
sed -i \
   -e 's/^INHERIT += "own-mirrors"/#INHERIT \+= "own-mirrors"/' \
   -e 's/^SOURCE_MIRROR_URL/#SOURCE_MIRROR_URL/' \
   -e 's/^SSTATE_MIRRORS/#SSTATE_MIRRORS/' \
   -e 's/^\#SSTATE_DIR ?= .*/SSTATE_DIR ?= "\/build\/common\/sstate-cache"/' \
   -e 's/^\#DL_DIR ?= .*/DL_DIR ?= "\/build\/common\/downloads"/' \
   conf/local.conf
echo "INHERIT += \"cve-check\"" >> conf/local.conf
bitbake freertos-demo
cd ..


export PYTHONPATH=/build/$project/$release/sources/poky/bitbake/lib

mkdir /build/$project/$release/tinfoilhat
mkdir /build/$project/$release/aliensrc
tinfoilhat $project $release /build/$project/$release/tinfoilhat "/build/$project/$release/linux-*" "/build/$project/$release/zephyr-*" "/build/$project/$release/freertos-*"
aliensrc_creator /build/$project/$release/aliensrc /build/$project/$release/tinfoilhat
