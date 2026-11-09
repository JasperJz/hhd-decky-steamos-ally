"""Manage the existing MangoApp HUD, without changing game launch options."""
import os
import asyncio
from mako_hud import read_live, format_sample
import subprocess
import threading
from pathlib import Path

# Display options only; no arbitrary commands or frame limit/driver changes.
GROUPS = {
    '帧率与画面': [('mako_fps','INPUT 原始帧率'),('fps','FPS 当前帧率'),('frametime','帧时间'),('frame_timing','帧时间曲线'),('frame_count','累计帧数'),('fps_metrics','平均帧率与 1% Low'),('histogram','帧时间直方图'),('refresh_rate','屏幕刷新率'),('resolution','分辨率'),('show_fps_limit','帧率上限'),('present_mode','呈现模式'),('hdr','HDR 状态'),('fsr','Gamescope FSR 状态'),('debug','Gamescope 帧时间与延迟图')],
    'CPU': [('cpu_stats','CPU 使用率'),('cpu_temp','CPU 温度'),('cpu_power','CPU 功耗'),('cpu_mhz','CPU 频率'),('core_load','各核心负载'),('core_bars','各核心柱状图')],
    'GPU': [('gpu_stats','GPU 使用率'),('gpu_temp','GPU 温度'),('gpu_junction_temp','GPU 热点温度'),('gpu_core_clock','GPU 核心频率'),('gpu_mem_clock','显存频率'),('gpu_mem_temp','显存温度'),('gpu_power','GPU 功耗'),('gpu_power_limit','GPU 功耗上限'),('gpu_voltage','GPU 电压'),('gpu_fan','GPU 风扇'),('throttling_status','降频状态'),('throttling_status_graph','降频状态曲线'),('gpu_name','GPU 名称'),('vulkan_driver','Vulkan 驱动')],
    '内存与磁盘': [('ram','内存占用'),('vram','显存占用'),('swap','交换空间'),('procmem','进程内存'),('procmem_shared','进程共享内存'),('procmem_virt','进程虚拟内存'),('io_read','进程磁盘读取'),('io_write','进程磁盘写入')],
    '电池与风扇': [('battery','电池电量'),('battery_watt','电池功耗'),('battery_time','预计续航'),('rog_fans','ROG 双风扇转速')],
    '系统与其他': [('time','当前时间'),('duration','运行时长'),('arch','程序架构'),('engine_version','引擎 / 图形接口'),('wine','Wine / Proton'),('gamemode','GameMode 状态'),('vkbasalt','vkBasalt 状态'),('exec_name','程序名称'),('version','MangoHud 版本'),('display_server','显示服务器'),('network','网络吞吐量')],
}
OPTIONS = {key: (group, label) for group, items in GROUPS.items() for key, label in items}
FANS = 'exec=/home/deck/.local/bin/rog-hud-fans'
SPECIAL = {'fps_metrics': 'fps_metrics=avg,0.01', 'network': 'network', 'rog_fans': FANS}
LEGACY_MAKO = ['exec=/usr/bin/python3 /home/deck/homebrew/plugins/hhd-decky/mako_hud.py ' + arg for arg in ('base', 'output')]
FPS_TEXT = Path('/home/deck/.cache/hhd-mako-hud/fps.txt')
MAKO_EXEC = {'mako_fps': 'exec=cat /home/deck/.cache/hhd-mako-hud/fps.txt'}
PARENTS = {
    **dict.fromkeys(('cpu_temp', 'cpu_power', 'cpu_mhz'), 'cpu_stats'),
    **dict.fromkeys(('gpu_temp', 'gpu_junction_temp', 'gpu_core_clock', 'gpu_power', 'gpu_voltage', 'gpu_fan'), 'gpu_stats'),
    **dict.fromkeys(('gpu_mem_clock', 'gpu_mem_temp'), 'vram'),
    **dict.fromkeys(('battery_watt', 'battery_time'), 'battery'),
    **dict.fromkeys(('procmem_shared', 'procmem_virt'), 'procmem'),
    'core_bars': 'core_load', 'frametime': 'fps', 'histogram': 'frame_timing',
    'throttling_status_graph': 'frame_timing', 'gpu_power_limit': 'gpu_power',
}
DISPLAY_ROWS = set('fps frame_timing core_load cpu_stats gpu_stats ram vram procmem io_read io_write arch wine gamemode vkbasalt engine_version vulkan_driver resolution show_fps_limit gpu_name battery fsr debug frame_count throttling_status exec_name duration fps_metrics hdr refresh_rate present_mode network display_server time version'.split())


def split_line(line):
    if line.strip().startswith('# hhd-disabled:'):
        return line.strip().split(':', 1)[1], '0'
    parts = line.strip().split('=', 1)
    return parts[0], parts[1].strip() if len(parts) > 1 else '1'


class PerformanceHUD:
    def __init__(self, config=None, reload=None):
        self.path = Path(config or '/home/deck/.config/MangoHud/output-hud.conf')
        self.reload = reload or self._reload
        self.lock = threading.Lock()

    async def sample_loop(self):
        def sample():
            value = read_live(Path('/home/deck/.config/mako-render/present-diagnostics.log'), FPS_TEXT.with_name('sample.json'))
            FPS_TEXT.parent.mkdir(parents=True, exist_ok=True)
            temporary = FPS_TEXT.with_name('fps.txt.tmp')
            temporary.write_text(format_sample(value) + '\n')
            os.replace(temporary, FPS_TEXT)
        try:
            while True:
                try:
                    await asyncio.to_thread(sample)
                except OSError:
                    pass
                await asyncio.sleep(1)
        finally:
            try:
                FPS_TEXT.write_text(format_sample(None) + '\n')
            except OSError:
                pass

    @staticmethod
    def _reload():
        # MangoApp uses a SysV control queue shared with Gamescope.
        subprocess.run(['/usr/bin/mangohudctl', 'set', 'reload_config', '1'],
                       check=True, timeout=3, capture_output=True, cwd='/home/deck')

    def _lines(self):
        if not self.path.is_file():
            raise ValueError('未找到当前 MangoApp 配置，尚未修改任何设置')
        return self.path.read_text().splitlines()

    def status(self):
        lines = self._lines()
        values = dict(split_line(line) for line in lines if line.strip() and not line.lstrip().startswith('#'))
        selected = {key: values.get(key, '0') not in ('0', 'false') for key in OPTIONS}
        selected['rog_fans'] = FANS in lines
        for key, command in MAKO_EXEC.items():
            selected[key] = command in lines or any(c in lines for c in LEGACY_MAKO)
        for _ in range(3):
            for child, parent in PARENTS.items():
                selected[child] = selected[child] and selected[parent]
        return {'ok': True, 'enabled': values.get('no_display', '0') in ('0', 'false'),
                'selected': selected,
                'groups': [{'title': group, 'items': [{'key': key, 'label': label} for key, label in items]} for group, items in GROUPS.items()],
                'notice': '部分指标需要硬件或游戏支持。温度、功耗等会联动开启对应 CPU/GPU 行；关闭该行会关闭其附属项。MAKO 双帧率需开启启动诊断并重启游戏；无新数据时显示 N/A。动态模式 FG req 为输出请求节奏，固定模式 FG 为提交计数，均非屏幕扫描测量。'}

    def update(self, changes=None, enabled=None):
        if changes is not None and (not isinstance(changes, dict) or any(k not in OPTIONS or type(v) is not bool for k, v in changes.items())):
            raise ValueError('监控选项无效')
        if enabled is not None and type(enabled) is not bool:
            raise ValueError('监控开关无效')
        with self.lock:
            lines = self._lines()
            original = '\n'.join(lines) + '\n'
            edits = dict(changes or {})
            combined = edits.get('mako_fps', any(c in lines for c in [*LEGACY_MAKO, *MAKO_EXEC.values()]))
            edits['mako_fps'] = combined
            lines = [line for line in lines if line.strip() not in LEGACY_MAKO]

            # MangoHud renders several subfields inside a parent row. Keep
            # switches honest instead of accepting an enabled but invisible item.
            for _ in range(3):
                for child, parent in PARENTS.items():
                    if edits.get(parent) is False and child not in edits:
                        edits[child] = False
                    if edits.get(child) is True:
                        edits[parent] = True
            replacements = {key: (SPECIAL.get(key, key) if value else key + '=0')
                            for key, value in edits.items() if key not in {'rog_fans', *MAKO_EXEC}}
            # In custom layout every named display row gets a separator even
            # when disabled. Preserve its order as a comment, not a live row.
            for key in DISPLAY_ROWS:
                if key in edits and not edits[key]:
                    replacements[key] = '# hhd-disabled:' + key
            # Migrate rows written by earlier versions on every update.
            for line in lines:
                key, value = split_line(line)
                if key in DISPLAY_ROWS and value in ('0', 'false') and key not in replacements:
                    replacements[key] = '# hhd-disabled:' + key
            if enabled is not None:
                replacements['no_display'] = 'no_display=' + ('0' if enabled else '1')
            # Preserve fonts, colours, layout and unrelated custom exec entries.
            updated, seen = [], set()
            for line in lines:
                key = split_line(line)[0]
                custom = next((k for k,c in MAKO_EXEC.items() if line.strip() == c), None)
                if custom and custom in edits:
                    if edits[custom] and custom not in seen:
                        updated.append(MAKO_EXEC[custom])
                    seen.add(custom)
                    continue
                if line.strip() == FANS and 'rog_fans' in edits:
                    if edits['rog_fans'] and 'rog_fans' not in seen:
                        updated.append(FANS)
                    seen.add('rog_fans')
                elif key in replacements:
                    if key not in seen:
                        updated.append(replacements[key])
                    seen.add(key)
                else:
                    updated.append(line)
            updated.extend(value for key, value in replacements.items() if key not in seen)
            if edits.get('rog_fans') and 'rog_fans' not in seen:
                updated.append(FANS)
            for key, command in MAKO_EXEC.items():
                if edits.get(key) and key not in seen:
                    updated.append(command)
            # Keep the FPS block first, immediately followed by its graph.
            front = []
            for key in ('fps',):
                match = next((line for line in updated if split_line(line)[0] == key), None)
                if match:
                    front.append(match)
            front.extend(line for line in updated if split_line(line)[0] == 'frame_timing')
            front.extend(line for line in updated if line in MAKO_EXEC.values())
            updated = front + [line for line in updated if line not in front]
            style = {'fps_text': 'FPS', 'engine_color': 'FF4040', 'fps_color_change': '0', 'fps_color': 'FF4040,FF4040,FF4040', 'fps_value': '0,1', 'hide_fps_superscript': '1'}
            updated = [line for line in updated if split_line(line)[0] not in style]
            updated.extend(key + '=' + value for key, value in style.items())
            lines = updated
            backup = self.path.with_name(self.path.name + '.before-hhd-manager')
            if not backup.exists():
                backup.write_text(original)
            # Replace atomically; the explicit control message reopens the new file.
            temporary = self.path.with_name(self.path.name + '.hhd-tmp')
            temporary.write_text('\n'.join(lines) + '\n')
            os.replace(temporary, self.path)
            try:
                self.reload()
            except Exception as error:
                self.path.write_text(original)
                try:
                    self.reload()
                except Exception:
                    pass
                raise ValueError('监控重载失败，已恢复配置：' + str(error)) from error
            return self.status()
