#!/bin/sh
# Build the SWEET-kernel (ios-sweet) guacamole boot images from board.<variant>.toml.
#   scripts/build-sweet-images.sh TAG [variant ...]   (default variants: probe gui)
set -eu
cd "$(dirname "$0")/.."
TAG=$1; shift
[ $# -gt 0 ] || set -- probe gui
FD=uefi/Build/SurfaceDuo1Pkg/DEBUG_CLANGPDB/FV/SM8150_EFI.fd
DTB=uefi/Platforms/SurfaceDuo1Pkg/Device/oneplus-guacamole/DeviceTreeBlob/Android/android-guacamole.dtb
cp board.toml board.orig.toml
trap 'mv board.orig.toml board.toml' EXIT
for v in "$@"; do
  cp "board.$v.toml" board.toml
  python3 scripts/build-payload.py > "out/guacamole/logs/payload-$v.txt" 2>&1 || { tail "out/guacamole/logs/payload-$v.txt"; exit 1; }
  cp out/guacamole/payload/payload.img "out/guacamole/payload/payload-$v.img"
  python3 scripts/build-bootimg.py --fd "$FD" --dtb "$DTB" --ramdisk "out/guacamole/payload/payload-$v.img" \
    -o "out/guacamole/boot/boot-$TAG-$v.img" | tail -1
done
