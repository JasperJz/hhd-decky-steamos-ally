"""On-demand X11/KWin workaround for Steam's desktop game keyboard window.

Runs only while the keyboard is open; no input text is read or recorded.
"""
import ctypes as C
import os
from pathlib import Path
import select
import signal
import subprocess
import time


def is_keyboard(caption):
    return 'keyboard' in caption.lower() or '屏幕键盘' in caption or '螢幕鍵盤' in caption


def choose_parent(windows, active, classes, names):
    group = classes.get(active, b'')
    if b'steam_app_' not in group:
        return active
    return next((w for w in reversed(windows)
                 if classes.get(w) == group and not is_keyboard(names.get(w, ''))), active)


class X11:
    def __init__(self, display):
        x = self.x = C.CDLL('libX11.so.6')
        def bind(name, result, args):
            f = getattr(x, name); f.restype = result; f.argtypes = args
        P, U, I = C.c_void_p, C.c_ulong, C.c_int
        bind('XOpenDisplay', P, [C.c_char_p])
        bind('XDefaultRootWindow', U, [P])
        bind('XInternAtom', U, [P, C.c_char_p, I])
        bind('XGetWindowProperty', I, [P,U,U,C.c_long,C.c_long,I,U,
             C.POINTER(U),C.POINTER(I),C.POINTER(U),C.POINTER(U),C.POINTER(P)])
        bind('XFree', I, [P])
        bind('XChangeProperty', I, [P,U,U,U,I,I,P,I])
        bind('XSetTransientForHint', I, [P,U,U])
        bind('XSelectInput', I, [P,U,C.c_long])
        bind('XFlush', I, [P])
        bind('XConnectionNumber', I, [P])
        bind('XPending', I, [P])
        bind('XNextEvent', I, [P,P])
        bind('XCloseDisplay', I, [P])
        self.handler = C.CFUNCTYPE(I,P,P)(lambda *_: 0)
        x.XSetErrorHandler.argtypes = [C.c_void_p]
        x.XSetErrorHandler(self.handler)
        self.d = x.XOpenDisplay(display.encode())
        if not self.d:
            raise RuntimeError('Cannot open desktop X11 display')
        self.root = x.XDefaultRootWindow(self.d)

    def prop(self, window, key):
        actual, fmt, count, remaining, data = C.c_ulong(),C.c_int(),C.c_ulong(),C.c_ulong(),C.c_void_p()
        status = self.x.XGetWindowProperty(self.d,window,self.x.XInternAtom(self.d,key.encode(),0),
                     0,4096,0,0,C.byref(actual),C.byref(fmt),C.byref(count),C.byref(remaining),C.byref(data))
        if status or not data.value:
            return []
        try:
            if fmt.value == 8:
                return C.string_at(data,count.value)
            if fmt.value == 32:
                return list(C.cast(data,C.POINTER(C.c_ulong))[:count.value])
            return []
        finally:
            self.x.XFree(data)

    def windows(self):
        return self.prop(self.root,'_NET_CLIENT_LIST_STACKING')

    def cardinal(self, window, key, value):
        data = C.c_ulong(value)
        self.x.XChangeProperty(self.d,window,self.x.XInternAtom(self.d,key.encode(),0),
             self.x.XInternAtom(self.d,b'CARDINAL',0),32,0,C.byref(data),1)
        self.x.XFlush(self.d)

    def caption(self, window):
        value = self.prop(window,'_NET_WM_NAME') or self.prop(window,'WM_NAME')
        return value.decode(errors='replace') if isinstance(value,bytes) else ''

    def wait_closed(self, window):
        self.x.XSelectInput(self.d,window,1 << 17)  # StructureNotifyMask
        self.x.XFlush(self.d)
        event = (C.c_long * 24)()
        while self.prop(window,'WM_CLASS'):
            if not self.x.XPending(self.d):
                select.select([self.x.XConnectionNumber(self.d)],[],[],5)
            while self.x.XPending(self.d):
                self.x.XNextEvent(self.d,event)
                if C.cast(event,C.POINTER(C.c_int))[0] == 17:
                    return  # Reparenting may briefly unmap; only destruction means closed.


def main():
    import fcntl
    import pwd
    def terminate(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM,terminate)
    lock = open('/run/hhd/desktop-keyboard.lock','a')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        return
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'comm').read_text().strip() == 'steam':
                uid = p.stat().st_uid
                raw = dict(v.split(b'=',1) for v in (p/'environ').read_bytes().split(b'\0') if b'=' in v)
                steam = str((p/'exe').resolve())
                break
        except OSError:
            continue
    else:
        raise RuntimeError('Steam is not running')
    user = pwd.getpwuid(uid)
    env = {k:raw[k.encode()].decode() for k in
           ['DISPLAY','XAUTHORITY','DBUS_SESSION_BUS_ADDRESS','XDG_RUNTIME_DIR','LANG'] if k.encode() in raw}
    env.update(HOME=user.pw_dir, PATH='/usr/bin:/bin')
    if not env.get('DISPLAY') or raw.get(b'XDG_SESSION_TYPE') != b'x11':
        subprocess.run([steam,'-ifrunning','steam://open/keyboard'],user=uid,group=user.pw_gid,env=env,check=False)
        return
    os.environ.update(env)
    def run(args):
        return subprocess.run(args,user=uid,group=user.pw_gid,env=env,
                              capture_output=True,text=True,timeout=5)
    def dbus(dest,path,method,*args):
        return run(['gdbus','call','--session','--dest',dest,'--object-path',path,'--method',method,*args])
    def compositing():
        return 'true' in dbus('org.kde.KWin','/Compositor',
                'org.freedesktop.DBus.Properties.Get','org.kde.kwin.Compositing','active').stdout
    def toggle_compositing():
        return run(['xdotool','key','--clearmodifiers','alt+shift+F12'])
    def show_desktop(show):
        showing = bool(next(iter(x.prop(x.root,'_NET_SHOWING_DESKTOP')),0))
        if showing != show:
            result = run(['xdotool','key','--clearmodifiers','super+d'])
            for _ in range(20):
                if bool(next(iter(x.prop(x.root,'_NET_SHOWING_DESKTOP')),0)) == show:
                    return result
                time.sleep(.05)
            raise RuntimeError('KWin show-desktop shortcut did not switch desktop')
    x = X11(env['DISPLAY'])
    active = next(iter(x.prop(x.root,'_NET_ACTIVE_WINDOW')),0)
    windows = x.windows()
    parent = choose_parent(windows,active,{w:x.prop(w,'WM_CLASS') for w in windows},
                           {w:x.caption(w) for w in windows})
    was_desktop = bool(next(iter(x.prop(x.root,'_NET_SHOWING_DESKTOP')),0))
    was_compositing = compositing()
    bypass = x.prop(active,'_NET_WM_BYPASS_COMPOSITOR')
    switched = False
    try:
        if bypass == [1]:
            x.cardinal(active,'_NET_WM_BYPASS_COMPOSITOR',0)
        if not was_compositing:
            toggle_compositing()
            time.sleep(.2)
        keyboard = next((w for w in x.windows() if is_keyboard(x.caption(w))),None)
        if not keyboard:
            if b'steam_app_' in x.prop(active,'WM_CLASS') and not was_desktop:
                show_desktop(True); switched = True; time.sleep(.3)
            result = run([steam,'-ifrunning','steam://open/keyboard'])
            if result.returncode:
                raise RuntimeError('Steam keyboard request failed')
            for _ in range(30):
                keyboard = next((w for w in x.windows() if is_keyboard(x.caption(w))),None)
                if keyboard:
                    break
                time.sleep(.1)
        if not keyboard:
            raise RuntimeError('Steam did not create a keyboard window')
        # The native window appears before Steam finishes initializing its keyboard.
        # Restoring game focus immediately can make Steam destroy that fresh window.
        time.sleep(.8)
        keyboard = next((w for w in x.windows() if is_keyboard(x.caption(w))),None)
        if not keyboard:
            raise RuntimeError('Steam keyboard closed during initialization')
        if parent and parent != keyboard:
            x.x.XSetTransientForHint(x.d,keyboard,parent)
            x.x.XFlush(x.d)
        if switched:
            show_desktop(False); switched = False
        print('Desktop keyboard window ready',flush=True)
        x.wait_closed(keyboard)
    finally:
        if switched:
            show_desktop(False)
        if bypass == [1]:
            x.cardinal(active,'_NET_WM_BYPASS_COMPOSITOR',1)
        if not was_compositing and compositing():
            toggle_compositing()
        x.x.XCloseDisplay(x.d)


if __name__ == '__main__':
    main()
