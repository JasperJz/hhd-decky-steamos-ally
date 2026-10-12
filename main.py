"""Decky -> local HHD Unix API. No tokens, second hardware daemon, or idle polling."""
import asyncio
import http.client
import json
import socket
import re
import time
from pathlib import Path
from urllib.parse import urlencode

MAINTENANCE = {'hhd.settings.update_stable', 'hhd.settings.update_beta'}


class HHDConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect('/run/hhd/api')


def request(method, endpoint, data=None):
    c = HHDConnection('localhost', timeout=4)
    try:
        payload = None if data is None else json.dumps(data)
        c.request(method, '/api/v1/' + endpoint, payload, {'Content-Type': 'application/json'})
        r = c.getresponse()
        body = r.read()
        if r.status != 200:
            raise ValueError('HHD API HTTP ' + str(r.status))
        return json.loads(body) if body else None
    finally:
        c.close()


def get_path(tree, path, default=None):
    for key in path.split('.'):
        if not isinstance(tree, dict) or key not in tree:
            return default
        tree = tree[key]
    return tree


def definitions(schema):
    out = {}
    def walk(node, path):
        if not isinstance(node, dict):
            return
        kind = node.get('type')
        if kind == 'container':
            for key, child in node.get('children', {}).items():
                walk(child, path + '.' + key)
        elif kind == 'mode':
            out[path + '.mode'] = {**node, 'type': 'multiple', 'options': node.get('modes', {})}
            for key, child in node.get('modes', {}).items():
                walk(child, path + '.' + key)
        elif kind:
            out[path] = node
        else:
            for key, child in node.items():
                walk(child, path + '.' + key if path else key)
    walk(schema, '')
    return out


def validate(schema, changes):
    defs = definitions(schema)
    if not isinstance(changes, list) or not 1 <= len(changes) <= 64:
        raise ValueError('修改列表无效')
    tree = {}
    for change in changes:
        path, value = change['path'], change['value']
        if path in MAINTENANCE:
            raise ValueError('此 SteamOS 安装请使用维护更新，内置更新会破坏依赖')
        node = defs.get(path)
        if not node:
            raise ValueError('当前设备没有此设置：' + path)
        kind = node['type']
        if kind in ('bool', 'action'):
            valid = isinstance(value, bool)
        elif kind == 'int':
            valid = type(value) is int and node['min'] <= value <= node['max']
        elif kind == 'multiple':
            valid = str(value) in node.get('options', {})
        elif kind == 'discrete':
            valid = value in node.get('options', [])
        else:
            valid = False
        if not valid:
            raise ValueError('设置值无效或只读：' + path)
        cursor = tree
        parts = path.split('.')
        for key in parts[:-1]:
            cursor = cursor.setdefault(key, {})
        cursor[parts[-1]] = value
    return tree


def hardware():
    def read(p):
        try:
            return Path(p).read_text().strip()
        except (OSError, ValueError):
            return None
    base = '/sys/devices/platform/asus-nb-wmi/'
    result = {key: read(base + key) for key in ('ppt_fppt', 'ppt_pl2_sppt', 'ppt_pl1_spl')}
    result['cpu_boost'] = read('/sys/devices/system/cpu/cpufreq/boost')
    for p in Path('/sys/class/power_supply').glob('BAT*/charge_control_end_threshold'):
        result['charge_limit'] = read(p)
    for p in Path('/sys/class/hwmon').glob('hwmon*'):
        name = read(p / 'name')
        if name == 'asus_custom_fan_curve':
            result['fan_custom'] = [read(p / ('pwm' + str(n) + '_enable')) for n in (1, 2)]
        elif name == 'asus':
            result['fan_rpm'] = [read(p / ('fan' + str(n) + '_input')) for n in (1, 2)]
        elif name == 'amdgpu':
            result['gpu_temp'] = read(p / 'temp1_input')
    return result


class Plugin:
    async def _main(self):
        self.lock = asyncio.Lock()
        self.cache = None

    async def _unload(self):
        pass

    def _snapshot(self):
        state = request('GET', 'state')
        version = state.get('version')
        if not getattr(self, 'cache', None) or self.cache[0] != version:
            self.cache = (version, request('GET', 'settings'), request('GET', 'sections'))
        return {'state': state, 'settings': self.cache[1], 'sections': self.cache[2],
                'hardware': hardware(), 'time': time.time()}

    async def snapshot(self, known_version=None):
        try:
            result = await asyncio.to_thread(Plugin._snapshot, self)
            if known_version is not None and known_version == result['state'].get('version'):
                result.pop('settings', None)
                result.pop('sections', None)
            return {'ok': True, **result}
        except Exception as e:
            return {'ok': False, 'error': 'HHD 后台未响应：' + str(e)}

    def _apply(self, changes):
        schema = request('GET', 'settings')
        payload = validate(schema, changes)
        state = request('POST', 'state', payload)
        # Actions automatically return to false; ordinary values must read back exactly.
        defs = definitions(schema)
        def mismatches(s):
            return [c['path'] for c in changes if defs[c['path']]['type'] != 'action'
                    and get_path(s, c['path']) != c['value']]
        # HHD's shared condition may wake on an unrelated hardware event before the
        # requested state is processed. A successful POST alone is not an acknowledgement.
        mismatch = mismatches(state)
        for _ in range(20):
            if not mismatch:
                break
            time.sleep(.15)
            state = request('GET', 'state')
            mismatch = mismatches(state)
        if mismatch:
            raise ValueError('后台未接受：' + ', '.join(mismatch))
        return {'ok': True, **Plugin._snapshot(self), 'written': changes}

    async def apply(self, changes):
        if not hasattr(self, 'lock'):
            self.lock = asyncio.Lock()
        async with self.lock:
            try:
                return await asyncio.to_thread(Plugin._apply, self, changes)
            except Exception as e:
                return {'ok': False, 'error': '修改未确认成功：' + str(e)}

    async def profiles(self, operation='list', name='', state=None, confirmed=False):
        if operation not in ('list', 'get', 'set', 'apply', 'del'):
            return {'ok': False, 'error': '配置操作无效'}
        if operation in ('apply', 'del') and not confirmed:
            return {'ok': False, 'error': '请确认配置操作'}
        if operation != 'list' and not name.strip():
            return {'ok': False, 'error': '请输入配置名称'}
        if operation != 'list' and re.sub(r'[^ a-zA-Z0-9]+', '', name) != name:
            return {'ok': False, 'error': 'HHD 配置名称仅支持英文字母、数字和空格'}
        endpoint = 'profile/' + operation
        if operation != 'list':
            endpoint += '?' + urlencode({'profile': name})
        try:
            data = state if operation == 'set' else None
            if operation == 'set':
                if not isinstance(state, dict):
                    return {'ok': False, 'error': '配置内容无效'}
                for key in MAINTENANCE:
                    if get_path(state, key):
                        return {'ok': False, 'error': '配置包含不兼容的自更新操作'}
                # Save configuration only, never transient actions, telemetry, or API internals.
                schema = await asyncio.to_thread(request, 'GET', 'settings')
                selected = []
                for path, node in definitions(schema).items():
                    if node['type'] not in ('bool', 'int', 'multiple', 'discrete'):
                        continue
                    if any(tag in node.get('tags', []) for tag in ('hide', 'hidden')):
                        continue
                    value = get_path(state, path)
                    if value is not None:
                        selected.append({'path': path, 'value': value})
                data = validate(schema, selected)
            return {'ok': True, 'result': await asyncio.to_thread(request, 'POST' if data else 'GET', endpoint, data)}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    async def diagnostics(self):
        try:
            return {'ok': True, 'api': await asyncio.to_thread(request, 'GET', 'version'),
                    'hardware': await asyncio.to_thread(hardware)}
        except Exception as e:
            return {'ok': False, 'error': str(e)}
