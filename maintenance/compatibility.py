"""Idempotent patches for the tested hhd4.1.12/adjustor4.0.1 SteamOS install."""
from pathlib import Path
import shutil

def patch(base=Path('/home/deck/.local/share/hhd/venv/lib/python3.13/site-packages')):
    def edit(relative, marker, old, new):
        p=base/relative;s=p.read_text()
        if marker in s:return
        if old not in s:raise RuntimeError('Unsupported source layout: '+relative)
        backup=Path('/var/lib/hhd-trial/maintenance-backups')/relative
        backup.parent.mkdir(parents=True,exist_ok=True)
        if not backup.exists():shutil.copy2(p,backup)
        s=s.replace(old,new,1);compile(s,str(p),'exec');p.write_text(s)
    line='            if upd_stable or upd_beta:\n'
    edit('hhd/__main__.py','# Local SteamOS install:',line,'''            # Local SteamOS install: upstream self-update removes adjustor and blocks the control loop.
            if (upd_stable or upd_beta) and os.environ.get("HHD_ALLOW_SELF_UPDATE") != "1":
                conf["hhd.settings.update_stable"] = False
                conf["hhd.settings.update_beta"] = False
                conf["hhd.settings.update_error"] = "SteamOS local installation: use the maintenance script to update HHD and adjustor together."
                logger.warning("Self-update blocked for managed SteamOS installation; hardware controls remain available.")
                upd_stable = upd_beta = False

'''+line)
    old='    elif is_in_cpu0(BOOST_FN):\n        set_per_cpu(BOOST_FN, "1" if enable else "0")'
    edit('adjustor/fuse/gpu.py','elif os.path.exists("/sys/devices/system/cpu/cpufreq/boost")',old,'''    elif os.path.exists("/sys/devices/system/cpu/cpufreq/boost"):
        with open("/sys/devices/system/cpu/cpufreq/boost", "w") as f:
            f.write("1" if enable else "0")
'''+old)
    old='new_boost = conf["tdp.amd_energy.mode.manual.cpu_boost"].to(bool)'
    edit('adjustor/drivers/gpu/__init__.py',old.replace('to(bool)','to(str)'),old,old.replace('to(bool)','to(str)'))
    old='''            case "event":
                self.set_response_ok()
                with self.cond:
'''
    new='''            case "event":
                if not content or not isinstance(content, Mapping):
                    return self.send_error("Event requires a POST with event data.")
                self.set_response_ok()
                with self.cond:
'''
    edit('hhd/http/api.py','Event requires a POST with event data.',old,new)
    old='''            case "state":
                self.set_response_ok()
'''
    new='''            case "state":
                if content is not None and not isinstance(content, Mapping):
                    return self.send_error("State content should be a dictionary.")
                self.set_response_ok()
'''
    edit('hhd/http/api.py','if content is not None and not isinstance(content, Mapping):',old,new)
if __name__=='__main__':
    patch();print('Compatibility patches present and valid')
