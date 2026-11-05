#!/usr/bin/env python3
"""Apply the ios-sweet bring-up userland changes (images v9-v14) to a mounted
iOS 16.7.16 (iPhone X, 20H392) HFS+ root.

    sudo python3 -I ios16-root-tweaks.py MOUNTPOINT

What and why (ios-sweet NOTES.md, 2026-10-16..18):
  - launchd.plist: _PanicOnCrash -> _PanicOnCrasX (a crashing daemon must not
    panic the kernel), CommCenter jobs removed (no modem: Setup/SpringBoard
    block in CoreTelephony XPC).
  - /private/var/containers/{Bundle,Data/System,Shared/SystemGroup,Temp}.
  - Data migration recorded as done for 20H392 in every place datamigrator
    looks, including the ByHost file for the ADT-derived IOPlatformUUID
    (unique-chip-id 0x5357454554000001 + chip-id 0x8015, same as sweet).
  - Setup skipped (purplebuddy), SpringBoard watchdogs off, no cloud config UI.
  - VirtualAudio HAL plug-in disabled (mediaserverd SIGSEGV loop) and the
    MediaToolbox recorder server not started (NULL GL prewarm crash loop).
"""
import os
import plistlib
import shutil
import sys
from pathlib import Path

BUILD = '20H392'
PLATFORM_UUID = 'A9683613-3704-53F2-95D0-98A8FB574E78'
MOBILE = 501
COMMCENTER = ('com.apple.CommCenter', 'com.apple.CommCenterRootHelper',
              'com.apple.CommCenterMobileHelper')


def write_plist(path, data, uid=MOBILE, gid=MOBILE, mode=0o600, merge=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    if merge and path.exists():
        with open(path, 'rb') as f:
            old = plistlib.load(f)
        old.update(data)
        data = old
    with open(path, 'wb') as f:
        plistlib.dump(data, f, fmt=plistlib.FMT_BINARY)
    os.chown(path, uid, gid)
    os.chmod(path, mode)
    print(f'plist {path}')


def mkdirs(root, rel, uid=0, gid=0, mode=0o755):
    p = root / rel
    p.mkdir(parents=True, exist_ok=True)
    os.chown(p, uid, gid)
    os.chmod(p, mode)


def main():
    root = Path(sys.argv[1])
    if not (root / 'System/Library/xpc/launchd.plist').is_file():
        sys.exit(f'{root}: not an iOS root')

    lp = root / 'System/Library/xpc/launchd.plist'
    with open(lp, 'rb') as f:
        launchd = plistlib.load(f)
    removed = []
    for key, job in list(launchd['LaunchDaemons'].items()):
        if '_PanicOnCrash' in job:
            job['_PanicOnCrasX'] = job.pop('_PanicOnCrash')
        if job.get('Label') in COMMCENTER:
            del launchd['LaunchDaemons'][key]
            removed.append(job['Label'])
    st = lp.stat()
    with open(lp, 'wb') as f:
        plistlib.dump(launchd, f, fmt=plistlib.FMT_BINARY)
    os.chown(lp, st.st_uid, st.st_gid)
    os.chmod(lp, st.st_mode & 0o7777)
    print(f'launchd.plist: removed {removed}')

    for rel in ('private/var/containers/Bundle', 'private/var/containers/Data/System',
                'private/var/containers/Shared/SystemGroup', 'private/var/containers/Temp'):
        mkdirs(root, rel)

    prefs = root / 'private/var/mobile/Library/Preferences'
    mkdirs(root, 'private/var/mobile/Library/Preferences', MOBILE, MOBILE, 0o755)
    mkdirs(root, 'private/var/mobile/Library/Preferences/ByHost', MOBILE, MOBILE, 0o755)
    write_plist(prefs / 'com.apple.migration.plist', {'LastSystemVersion': BUILD})
    write_plist(prefs / 'com.apple.DataMigration.plist', {'LastSystemVersion': BUILD})
    for u in (PLATFORM_UUID, PLATFORM_UUID.lower()):
        write_plist(prefs / f'ByHost/com.apple.migration.{u}.plist', {'LastSystemVersion': BUILD})

    write_plist(prefs / 'com.apple.purplebuddy.plist', {
        'SetupDone': True, 'SetupFinishedAllSteps': True, 'SetupVersion': 11,
        'daemonizeNeedsToRun': False})
    write_plist(prefs / 'com.apple.springboard.plist', {
        'BKNoWatchdogs': True,
        'FBLaunchWatchdogExceptions': {'com.apple.purplebuddy': 100},
        'MCForceShowCloudConfigurationUI': False})
    write_plist(prefs / 'com.apple.managedconfiguration.notbackedup.plist', {
        'LockdownActivationIndicatesCloudConfigurationAvailable': False})

    hal = root / 'Library/Audio/Plug-Ins/HAL'
    va = hal / 'VirtualAudio.plugin'
    if va.exists():
        dis = root / 'Library/Audio/Plug-Ins/HAL.disabled'
        dis.mkdir(exist_ok=True)
        shutil.move(str(va), str(dis / 'VirtualAudio.plugin'))
        print('VirtualAudio.plugin disabled')

    # MediaToolbox: StartRecorderServer=false in every SubServerConfiguration.
    mt = [root / 'System/Library/Frameworks/MediaToolbox.framework']
    mt += list((root / 'private/preboot/Cryptexes').glob('*/System/Library/Frameworks/MediaToolbox.framework'))
    for fw in mt:
        for p in fw.rglob('*.plist'):
            try:
                with open(p, 'rb') as f:
                    data = plistlib.load(f)
            except Exception:
                continue
            changed = []

            def walk(o, path=''):
                if isinstance(o, dict):
                    if 'StartRecorderServer' in o and o['StartRecorderServer'] is not False:
                        o['StartRecorderServer'] = False
                        changed.append(path)
                    for k, v in o.items():
                        walk(v, f'{path}/{k}')
                elif isinstance(o, list):
                    for i, v in enumerate(o):
                        walk(v, f'{path}[{i}]')
            walk(data)
            if changed:
                st = p.stat()
                fmt = plistlib.FMT_BINARY if p.read_bytes()[:6] == b'bplist' else plistlib.FMT_XML
                with open(p, 'wb') as f:
                    plistlib.dump(data, f, fmt=fmt)
                os.chmod(p, st.st_mode & 0o7777)
                print(f'{p}: StartRecorderServer=false at {changed}')


if __name__ == '__main__':
    main()
