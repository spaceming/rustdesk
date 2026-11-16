#!/usr/bin/env bash
set -euo pipefail
. /root/.cargo/env
export PKG_CONFIG_PATH=/work/pkgconfig
export CARGO_TARGET_DIR=/work/rustdesk/target
export CARGO_PROFILE_DEV_DEBUG=0
export CARGO_PROFILE_TEST_DEBUG=0
export CARGO_INCREMENTAL=0
export CARGO_BUILD_JOBS=2
cd /work/rustdesk16703
cp /work/16703-artifacts/cursor_probe.rs examples/cursor_probe.rs
cp /work/16703-artifacts/cursor_network.rs examples/cursor_network.rs
cargo build --locked --bin rustdesk --example cursor_probe --example cursor_network --features linux-pkg-config,drm
cp "$CARGO_TARGET_DIR/debug/examples/cursor_probe" /work/16703-artifacts/cursor-probe-baseline
cp "$CARGO_TARGET_DIR/debug/examples/cursor_network" /work/16703-artifacts/cursor-network-baseline
cp "$CARGO_TARGET_DIR/debug/rustdesk" /work/16703-artifacts/rustdesk-baseline
cp /work/16703-artifacts/linux-fixed.rs src/platform/linux.rs
cargo build --locked --bin rustdesk --example cursor_probe --example cursor_network --features linux-pkg-config,drm
cp "$CARGO_TARGET_DIR/debug/examples/cursor_probe" /work/16703-artifacts/cursor-probe-fixed
cp "$CARGO_TARGET_DIR/debug/examples/cursor_network" /work/16703-artifacts/cursor-network-fixed
cp "$CARGO_TARGET_DIR/debug/rustdesk" /work/16703-artifacts/rustdesk-fixed
cargo test --locked --lib --features linux-pkg-config,drm cursor_image_tests -- --nocapture
ldd /work/16703-artifacts/rustdesk-fixed
