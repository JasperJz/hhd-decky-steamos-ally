"""On-device Steam/Decky layout and module navigation audit using local CEF debugging."""
import base64
import json
from pathlib import Path
import time
import urllib.request
import websocket

pages = json.load(urllib.request.urlopen('http://127.0.0.1:8080/json/list'))
page = next(p for p in pages if 'QuickAccess' in p['title'])
ws = websocket.create_connection(page['webSocketDebuggerUrl'], origin='http://localhost', timeout=20)
sequence = 0
errors = []


def call(method, params):
    global sequence
    sequence += 1
    ws.send(json.dumps({'id': sequence, 'method': method, 'params': params}))
    while True:
        result = json.loads(ws.recv())
        if result.get('method') == 'Runtime.exceptionThrown':
            errors.append(result['params'])
        if result.get('id') == sequence:
            assert 'error' not in result, result
            return result['result']


def evaluate(expression):
    result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True,
                                       'awaitPromise': True})
    assert 'exceptionDetails' not in result, result
    return result.get('result', {}).get('value')


def screenshot(name):
    result = call('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
    (out / (name + '.png')).write_bytes(base64.b64decode(result['data']))


out = Path('/home/deck/.local/state/hhd-recovery/ui-audit')
out.mkdir(exist_ok=True)
call('Runtime.enable', {})
if evaluate("document.querySelector('[data-hhd-page]')?.dataset.hhdPage") != 'home':
    evaluate("[...document.querySelectorAll('button')].find(e=>e.textContent.includes('返回模块'))?.click()")
    time.sleep(.3)
ids = evaluate("[...document.querySelectorAll('[data-hhd-module]')].map(e=>e.dataset.hhdModule)")
assert len(ids) == 12 and '__hud' in ids, ids
rects = evaluate("[...document.querySelectorAll('[data-hhd-module]')].map(e=>({id:e.dataset.hhdModule,...e.getBoundingClientRect().toJSON(),overflow:e.scrollWidth-e.clientWidth}))")
for i, rect in enumerate(rects):
    assert rect['overflow'] <= 1, rect
    for other in rects[i + 1:]:
        assert (rect['right'] <= other['left'] + 1 or other['right'] <= rect['left'] + 1
                or rect['bottom'] <= other['top'] + 1 or other['bottom'] <= rect['top'] + 1), (rect, other)
screenshot('home')
report = []
for module in ids:
    evaluate("(()=>{const b=document.querySelector('[data-hhd-module=\"" + module + "\"]');b.scrollIntoView({block:'center'});b.click();})()")
    time.sleep(.4)
    assert evaluate("document.querySelector('[data-hhd-page]')?.dataset.hhdPage") == module
    text = evaluate("document.querySelector('[data-hhd-page]').innerText")
    assert '返回模块' in text, module
    assert '设置分类' not in text, module
    # Validate every visible interactive control fits horizontally inside the page.
    overflow = evaluate("(()=>{const p=document.querySelector('[data-hhd-page]'),r=p.getBoundingClientRect();return [...p.querySelectorAll('button,input,[role=slider]')].filter(e=>{const b=e.getBoundingClientRect();return b.width>0&&(b.left<r.left-2||b.right>r.right+2)}).map(e=>({text:e.textContent,rect:e.getBoundingClientRect().toJSON(),page:r.toJSON()}))})()")
    assert not overflow, (module, overflow)
    evaluate("document.querySelector('[data-hhd-page]').scrollIntoView({block:'start'})")
    screenshot(module)
    evaluate("[...document.querySelectorAll('button')].find(e=>e.textContent.includes('返回模块')).click()")
    time.sleep(.2)
    assert evaluate("document.querySelector('[data-hhd-page]')?.dataset.hhdPage") == 'home'
    report.append({'module': module, 'navigation': 'passed', 'horizontal_layout': 'passed'})
    print('PASS', module, flush=True)
assert not errors, errors
(out / 'report.json').write_text(json.dumps(report, indent=2))
print('PASS all 12 modules, return navigation, card alignment, control bounds, no runtime exceptions')
ws.close()
