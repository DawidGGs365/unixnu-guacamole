#!/bin/bash
# Build the iOS 16.7.16 (iPhone X, 20H392) HFS+ userdata root for the SWEET
# kernel chain (rd=ufsroot0): ios-sweet tools/mkiosroot.sh + the ios-sweet
# v9-v14 userland changes (scripts/ios16-root-tweaks.py), then a sparse image.
#
#   scripts/build-ios16-root.sh IPSW OUTDIR [SIZE]      (SIZE default 16G)
#
# Run as your user; it calls sudo for apfs-fuse, the loop mount and chown.
# Output: OUTDIR/ios16-root-20H392.img and .simg (for fastboot flash).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
ipsw=$(realpath "$1") out=$(realpath -m "$2") size=${3:-16G}
mkiosroot=${MKIOSROOT:-$here/mkiosroot-guac.sh}
[[ -x $mkiosroot ]] || { echo "missing $mkiosroot" >&2; exit 1; }
mkdir -p "$out/dmg"
img=$out/ios16-root-20H392.img
if [[ -e $img && ${RESUME:-0} != 1 ]]; then echo "refusing to overwrite $img (RESUME=1 continues into it)" >&2; exit 1; fi
export RESUME=${RESUME:-0}

# BuildManifest (d22ap): OS 087-86698-044, SystemOS 087-86593-047, AppOS 087-86715-047
for d in 087-86698-044.dmg 087-86593-047.dmg 087-86715-047.dmg; do
	[[ -s $out/dmg/$d ]] || unzip -o -q "$ipsw" "$d" -d "$out/dmg"
done
"$mkiosroot" "$out/dmg/087-86698-044.dmg" "$out/dmg/087-86593-047.dmg" \
	"$out/dmg/087-86715-047.dmg" "$img" "$size"

mnt=$(mktemp -d)
sudo mount -t hfsplus -o loop,force "$img" "$mnt"
trap 'sudo umount "$mnt" 2>/dev/null; rmdir "$mnt" 2>/dev/null || true' EXIT
sudo python3 -I "$here/ios16-root-tweaks.py" "$mnt"
sync
sudo umount "$mnt"
trap - EXIT
rmdir "$mnt"
fsck.hfsplus -f -y "$img" | grep -v 'Illegal name' || true
fsck.hfsplus -f -n "$img"
img2simg "$img" "$img.simg"
sha256sum "$img" "$img.simg" | tee "$img.sha256"
echo "done: $img.simg"
