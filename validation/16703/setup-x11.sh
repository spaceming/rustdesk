#!/usr/bin/env bash
set -euo pipefail
# Run in the existing Debian RustDesk build container, not on the host.
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends xvfb tigervnc-standalone-server \
  tigervnc-viewer x11-utils x11-apps xdotool openbox python3-pil python3-xlib \
  libxrender-dev libxcursor-dev
mkdir -p /work/rustdesk16703/libs/hbb_common /work/16703-artifacts
tar -xf /work/16703-source.tar -C /work/rustdesk16703
tar -xf /work/16703-hbb.tar -C /work/rustdesk16703/libs/hbb_common
