#!/usr/bin/env python3
"""Exercise the real RustDesk cursor API against an X11 TigerVNC viewer."""
import json
import os
from pathlib import Path
import selectors
import subprocess
import time

from Xlib import X, Xcursorfont, display
from Xlib.ext import xtest
from PIL import Image

OUT = Path('/work/16703-artifacts')
processes = []

def launch(args, name, env=None):
    log = open(OUT / (name + '.log'), 'w')
    p = subprocess.Popen(args, stdout=log, stderr=log, env=env)
    processes.append(p)
    return p

def connect(name):
    for _ in range(100):
        try:
            return display.Display(name)
        except Exception:
            time.sleep(.1)
    raise RuntimeError('X server did not start: ' + name)

def probe(binary, env):
    p = subprocess.Popen([str(OUT / binary)], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=open(OUT / (binary+'.log'), 'w'),
                         text=True, env=env, bufsize=1)
    processes.append(p)
    return p

def read(p, label):
    p.stdin.write(label + '\n')
    p.stdin.flush()
    ready = selectors.DefaultSelector()
    ready.register(p.stdout, selectors.EVENT_READ)
    if not ready.select(10):
        raise RuntimeError('probe timeout: ' + label)
    result = json.loads(p.stdout.readline())
    ready.close()
    return result

try:
    launch(['Xvfb', ':91', '-screen', '0', '1024x768x24', '-ac', '-nolisten', 'tcp'], 'xvfb')
    host = connect(':91')
    launch(['Xtigervnc', ':92', '-geometry', '640x480', '-depth', '24',
            '-SecurityTypes', 'None', '-localhost', 'yes', '-rfbport', '5992',
            '-ac', '-nolisten', 'tcp'], 'vnc-server')
    nested = connect(':92')
    root = host.screen().root
    font = host.open_font('cursor')
    arrow = font.create_glyph_cursor(font, Xcursorfont.left_ptr, Xcursorfont.left_ptr+1,
                                     (0,0,0), (65535,65535,65535))
    root.change_attributes(background_pixel=0x52708a, cursor=arrow)
    root.clear_area()
    nr = nested.screen().root
    nr.change_attributes(background_pixel=0x335d3a)
    nr.clear_area()
    # A real remote application window with an intentionally hidden X cursor.
    window = nr.create_window(50, 50, 500, 350, 0, nested.screen().root_depth,
                              X.InputOutput, X.CopyFromParent, background_pixel=0xdddddd)
    window.set_wm_name('Nested application hides its system cursor')
    pixmap = nr.create_pixmap(1, 1, 1)
    gc = pixmap.create_gc(foreground=0)
    pixmap.fill_rectangle(gc, 0, 0, 1, 1)
    blank = pixmap.create_cursor(pixmap, (0,0,0), (0,0,0), 0, 0)
    window.change_attributes(cursor=blank)
    window.map()
    nested.sync()
    env = dict(os.environ, DISPLAY=':91', XDG_SESSION_TYPE='x11',
               RUSTDESK_FORCED_DISPLAY_SERVER='x11')
    launch(['vncviewer', '-SecurityTypes', 'None', '-Shared', '-AlwaysCursor=0', '-geometry',
            '640x480+200+100', '127.0.0.1::5992'], 'vnc-viewer', env)
    time.sleep(2)
    children = root.query_tree().children
    for child in children:
        if child.get_geometry().width == 640:
            child.set_input_focus(X.RevertToParent, X.CurrentTime)
    root.warp_pointer(50,50)
    host.sync()
    time.sleep(.3)
    baseline = probe('cursor-probe-baseline', env)
    fixed = probe('cursor-probe-fixed', env)
    results = []
    def sample(label, x, y):
        xtest.fake_input(host, X.MotionNotify, x=x-5, y=y-5)
        host.sync()
        time.sleep(.2)
        xtest.fake_input(host, X.MotionNotify, x=x, y=y)
        host.sync()
        time.sleep(.5)
        row = {'label':label, 'baseline':read(baseline,label), 'fixed':read(fixed,label)}
        results.append(row)
        print(json.dumps(row), flush=True)
        return row
    before = sample('outside-before',50,50)
    inside = sample('inside-hidden-vnc',400,300)
    # Start a new cursor reader while the real VNC window has a blank cursor.
    fresh_baseline, fresh_fixed = probe('cursor-probe-baseline',env), probe('cursor-probe-fixed',env)
    fresh = {'label':'starts-hidden', 'baseline':read(fresh_baseline,'starts-hidden'),
             'fixed':read(fresh_fixed,'starts-hidden')}
    results.append(fresh)
    print(json.dumps(fresh),flush=True)
    screenshot = root.get_image(0,0,1024,768,X.ZPixmap,0xffffffff)
    Image.frombytes('RGB',(1024,768),screenshot.data,'raw','BGRX').save(OUT/'x11-vnc.png')
    after = sample('outside-after',50,50)
    again = sample('inside-hidden-vnc-again',400,300)
    checks = {
        'baseline-visible-before': before['baseline'].get('visible_pixels',0)>0,
        'baseline-sends-transparent-image-in-vnc': inside['baseline'].get('visible_pixels')==0,
        'fixed-skips-transparent-image-in-vnc': inside['fixed']['id'] is None,
        'baseline-starts-with-transparent-image': fresh['baseline'].get('visible_pixels')==0,
        'fixed-starts-hidden-with-no-shape': fresh['fixed']['id'] is None,
        'fixed-normal-shape-restored': after['fixed'].get('visible_pixels',0)>0,
        'normal-shape-unchanged': before['baseline']==before['fixed'] and after['baseline']==after['fixed'],
        'repeat-hidden-transition': again['fixed']['id'] is None and again['baseline'].get('visible_pixels')==0,
    }
    (OUT/'x11-result.json').write_text(json.dumps({'results':results,'checks':checks},indent=2))
    print(json.dumps(checks),flush=True)
    assert all(checks.values()), 'Some X11/VNC checks failed'
    if os.environ.get('RUN_NETWORK'):
        network_results = {}
        net_checks = {}
        for mode in ['baseline', 'fixed']:
            ibeam = font.create_glyph_cursor(font, Xcursorfont.xterm, Xcursorfont.xterm+1,
                                             (0,0,0),(65535,65535,65535))
            root.change_attributes(cursor=ibeam)
            xtest.fake_input(host,X.MotionNotify,x=50,y=50)
            host.sync()
            time.sleep(.3)
            netenv = dict(env,XDG_CONFIG_HOME=str(OUT/('config-'+mode)))
            server = launch([str(OUT/('cursor-network-'+mode)),'server'], 'network-server-'+mode, netenv)
            time.sleep(1)
            client = launch([str(OUT/('cursor-network-'+mode)),'client'], 'network-client-'+mode, netenv)
            time.sleep(2)
            def events():
                return [json.loads(line) for line in (OUT/('network-client-'+mode+'.log')).read_text().splitlines() if line.startswith('{')]
            first = events()
            xtest.fake_input(host,X.MotionNotify,x=390,y=290)
            host.sync()
            time.sleep(.2)
            xtest.fake_input(host,X.MotionNotify,x=400,y=300)
            host.sync()
            time.sleep(1)
            entered = events()
            snapshot_client = launch([str(OUT/('cursor-network-'+mode)),'client'], 'network-snapshot-'+mode, netenv)
            time.sleep(1)
            snapshot_client.terminate()
            snapshot_client.wait(timeout=5)
            snapshot = [json.loads(line) for line in (OUT/('network-snapshot-'+mode+'.log')).read_text().splitlines() if line.startswith('{')]
            root.change_attributes(cursor=arrow)
            xtest.fake_input(host,X.MotionNotify,x=50,y=50)
            host.sync()
            time.sleep(1)
            left = events()
            network_results[mode] = {'before':first,'inside':entered[len(first):], 'after':left[len(entered):], 'snapshot_while_hidden':snapshot}
            client.terminate()
            server.terminate()
            client.wait(timeout=5)
            server.wait(timeout=5)
            time.sleep(.5)
            xtest.fake_input(host,X.MotionNotify,x=390,y=290)
            host.sync()
            time.sleep(.2)
            xtest.fake_input(host,X.MotionNotify,x=400,y=300)
            host.sync()
            time.sleep(.3)
            hidden_server = launch([str(OUT/('cursor-network-'+mode)),'server'], 'network-hidden-server-'+mode, netenv)
            time.sleep(1)
            hidden_client = launch([str(OUT/('cursor-network-'+mode)),'client'], 'network-hidden-client-'+mode, netenv)
            time.sleep(2)
            hidden_client.terminate()
            hidden_server.terminate()
            hidden_client.wait(timeout=5)
            hidden_server.wait(timeout=5)
            hidden = [json.loads(line) for line in (OUT/('network-hidden-client-'+mode+'.log')).read_text().splitlines() if line.startswith('{')]
            network_results[mode]['server_starts_hidden'] = hidden
            def cursors(rows):
                return [r for r in rows if r['event']=='cursor']
            rows=network_results[mode]
            net_checks[mode+'-login-succeeds']=any(r['event']=='login' and 'PeerInfo' in r['response'] for r in first)
            net_checks[mode+'-initial-visible']=any(r['visible_pixels']>0 for r in cursors(first))
            net_checks[mode+'-new-visible-shape-after-exit']=any(r['visible_pixels']>0 for r in cursors(rows['after']))
            if mode=='baseline':
                net_checks['baseline-transmits-transparent']=any(r['visible_pixels']==0 for r in cursors(rows['inside']))
                net_checks['baseline-hidden-snapshot-transparent']=any(r['visible_pixels']==0 for r in cursors(snapshot))
                net_checks['baseline-hidden-start-transparent']=any(r['visible_pixels']==0 for r in cursors(hidden))
            else:
                net_checks['fixed-retains-existing-shape']=not cursors(rows['inside'])
                net_checks['fixed-hidden-snapshot-visible']=any(r['visible_pixels']>0 for r in cursors(snapshot))
                net_checks['fixed-hidden-start-does-not-blank-default']=not cursors(hidden) and any(r['event']=='login' and 'PeerInfo' in r['response'] for r in hidden)
            time.sleep(.5)
        (OUT/'network-result.json').write_text(json.dumps(network_results,indent=2))
        (OUT/'network-checks.json').write_text(json.dumps(net_checks,indent=2))
        print(json.dumps(net_checks),flush=True)
        assert all(net_checks.values()), 'Some actual TCP cursor service checks failed'
finally:
    for p in reversed(processes):
        if p.poll() is None:
            p.terminate()
    for p in reversed(processes):
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
