"""Explicit on-device regression audit. Temporarily changes safe settings, then restores them.

Run with the HHD venv Python as root after backing up the device configuration.
Never invokes reboot/reset/hibernate, firmware updates, or controller mode changes.
"""
import asyncio
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, '/home/deck/homebrew/plugins/hhd-decky')
from main import Plugin, definitions, get_path, request, hardware


async def audit():
    plugin = Plugin()
    await plugin._main()
    original = (await plugin.snapshot())['state']
    schema = request('GET', 'settings')
    defs = definitions(schema)
    report = []
    profile = 'HHD Regression Temporary'

    async def apply(changes):
        result = await plugin.apply(changes)
        assert result['ok'], result.get('error')
        return result

    async def exercise(path, value, check=None):
        old = get_path(original, path)
        if path not in defs or old is None:
            report.append({'path': path, 'status': 'unsupported'})
            return
        try:
            result = await apply([{'path': path, 'value': value}])
            assert get_path(result['state'], path) == value
            if check:
                for _ in range(30):
                    if check(hardware()):
                        break
                    await asyncio.sleep(.1)
                else:
                    raise AssertionError('Hardware readback mismatch: ' + path)
            report.append({'path': path, 'status': 'passed'})
            print('PASS', path, flush=True)
        finally:
            await apply([{'path': path, 'value': old}])

    try:
        current_controls = [
            {'path': path, 'value': get_path(original, path)}
            for path, node in defs.items()
            if node['type'] in ('bool', 'int', 'multiple', 'discrete')
            and not any(t in node.get('tags', []) for t in ('hide', 'hidden'))
            and get_path(original, path) is not None
        ]
        for i in range(0, len(current_controls), 32):
            await apply(current_controls[i:i + 32])
        report.append({'feature': 'all available setting writes and API readbacks',
                       'count': len(current_controls), 'status': 'passed'})
        print('PASS', len(current_controls), 'setting writes and API readbacks', flush=True)
        # Test the actual preset -> custom transition which previously lied about success.
        await apply([{'path': 'tdp.asus.tdp_v2.mode', 'value': 'performance'}])
        await exercise('tdp.asus.tdp_v2.custom.tdp', 14,
                       lambda h: h['ppt_pl1_spl'] == '14')
        await exercise('tdp.amd_energy.mode.manual.cpu_boost', 'enabled',
                       lambda h: h['cpu_boost'] == '1')
        await exercise('tdp.battery.charge_limit', 'p80',
                       lambda h: h['charge_limit'] == '80')
        await exercise('tdp.asus.fan.manual.st40', 22)
        await exercise('tdp.amd_energy.gpu_freq.range.max', 1600)
        mode = get_path(original, 'rgb.handheld.mode.mode')
        brightness = f'rgb.handheld.mode.{mode}.brightnessd'
        if brightness in defs:
            await exercise(brightness, 'medium')
        await exercise('shortcuts.touchscreen.top', 'disabled')
        await exercise('controllers.rog_ally.rgb_charging',
                       not get_path(original, 'controllers.rog_ally.rgb_charging'))

        result = await plugin.profiles('set', profile, original)
        assert result['ok'], result
        assert profile in (await plugin.profiles())['result']
        saved = await plugin.profiles('get', profile)
        assert saved['ok'], saved
        assert get_path(saved['result'], 'tdp.asus.tdp_v2.custom.tdp') == 15
        await apply([{'path': 'tdp.asus.tdp_v2.custom.tdp', 'value': 14}])
        applied = await plugin.profiles('apply', profile, confirmed=True)
        assert applied['ok'], applied
        await asyncio.sleep(2)
        assert get_path(request('GET', 'state'), 'tdp.asus.tdp_v2.custom.tdp') == 15
        assert hardware()['ppt_pl1_spl'] == '15'
        # A new plugin instance must see profiles persisted by the daemon.
        fresh = Plugin()
        assert profile in (await fresh.profiles())['result']
        removed = await fresh.profiles('del', profile, confirmed=True)
        assert removed['ok'], removed
        assert profile not in (await fresh.profiles())['result']
        report.append({'feature': 'profile CRUD, apply hardware, fresh instance', 'status': 'passed'})
        print('PASS profile CRUD, apply hardware, fresh instance', flush=True)

        color = await plugin.color()
        assert color['ok'], color
        try:
            changed = await plugin.color(preset='natural')
            assert changed['ok'] and changed['color']['saturation'] == 110, changed
        finally:
            restored = await plugin.color(changes=color['color'], enabled=color['enabled'])
            assert restored['ok'], restored
        report.append({'feature': 'screen-color preset and restoration', 'status': 'passed'})
        print('PASS screen-color preset and restoration', flush=True)
    finally:
        await apply([{'path': 'tdp.asus.tdp_v2.mode', 'value': 'custom'},
                     {'path': 'tdp.asus.tdp_v2.custom.tdp', 'value': 15},
                     {'path': 'tdp.asus.tdp_v2.custom.boost', 'value': False}])
        names = await plugin.profiles()
        if names['ok'] and profile in names['result']:
            await plugin.profiles('del', profile, confirmed=True)
    output = Path('/home/deck/.local/state/hhd-recovery/live-audit.json')
    output.write_text(json.dumps({'time': time.time(), 'results': report,
                                 'hardware': hardware()}, indent=2))
    print('REPORT', output, flush=True)


if __name__ == '__main__':
    if sys.argv[1:] != ['--exercise']:
        raise SystemExit('Requires --exercise on the SteamOS device; temporarily changes hardware settings.')
    asyncio.run(audit())
