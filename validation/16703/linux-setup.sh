#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  build-essential cmake ninja-build pkg-config curl git ca-certificates clang libclang-dev \
  nasm yasm protobuf-compiler zip unzip python3 python3-evdev python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
  libgtk-3-dev libxdo-dev libxfixes-dev libxcb-randr0-dev libxcb-shape0-dev libxcb-xfixes0-dev \
  libasound2-dev libpulse-dev libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libssl-dev \
  libvpx-dev libyuv-dev libopus-dev libaom-dev libdbus-1-dev libv4l-dev libva-dev libudev-dev \
  libunwind-dev libpam0g-dev libxtst-dev libxrandr-dev libxinerama-dev libxcursor-dev \
  libxkbcommon-dev libxkbcommon-x11-dev libinput-tools evtest seatd sway swaybg \
  weston xwayland wayland-utils wlr-randr grim dbus-x11 udev
curl --fail --silent --show-error --location https://sh.rustup.rs -o /tmp/rustdesk-rustup.sh
sh /tmp/rustdesk-rustup.sh -y --profile minimal --default-toolchain 1.91.1
mkdir -p /work
cp -a /source /work/rustdesk
mkdir -p /work/pkgconfig
if ! pkg-config --exists libyuv; then
  cat >/work/pkgconfig/libyuv.pc <<'EOF'
prefix=/usr
includedir=${prefix}/include
libdir=${prefix}/lib/x86_64-linux-gnu

Name: libyuv
Description: System libyuv installed from Debian libyuv-dev
Version: 0.0
Libs: -L${libdir} -lyuv
Cflags: -I${includedir}
EOF
fi
. /root/.cargo/env
rustc --version
PKG_CONFIG_PATH=/work/pkgconfig pkg-config --modversion vpx libyuv opus aom
