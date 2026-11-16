#!/usr/bin/env python3
"""Run an isolated Flutter controller, X11 host and nested TigerVNC desktop."""
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time

from Xlib import X, Xcursorfont, display
from Xlib.ext import xtest

OUT=Path('/work/16703-gui')
ART=Path('/work/16703-artifacts')
processes={}
client_env=dict(os.environ,DISPLAY=':93',XDG_SESSION_TYPE='x11',
                RUSTDESK_FORCED_DISPLAY_SERVER='x11',LIBGL_ALWAYS_SOFTWARE='1',
                XDG_CONFIG_HOME=str(OUT/'config-controller'),
                XDG_DATA_HOME=str(OUT/'data-controller'))
host_env=dict(os.environ,DISPLAY=':91',XDG_SESSION_TYPE='x11',
              RUSTDESK_FORCED_DISPLAY_SERVER='x11')

def launch(name,args,env=None):
    p=subprocess.Popen(args,stdout=open(OUT/(name+'.log'),'a'),stderr=subprocess.STDOUT,
                       env=env,start_new_session=True)
    processes[name]=p
    return p

def stop(name):
    p=processes.pop(name,None)
    if p and p.poll() is None:
        os.killpg(p.pid,signal.SIGTERM)
        try: p.wait(timeout=4)
        except subprocess.TimeoutExpired: os.killpg(p.pid,signal.SIGKILL)

def connect(name):
    for _ in range(100):
        try: return display.Display(name)
        except Exception: time.sleep(.1)
    raise RuntimeError('Cannot open '+name)

def cursor_probe(target,label):
    p=subprocess.run([str(ART/'cursor-probe-baseline')],input=label+'\nquit\n',
                     capture_output=True,text=True,env=dict(host_env,DISPLAY=target),check=True)
    return json.loads(p.stdout.strip())

try:
    launch('host-xvfb',['Xvfb',':91','-screen','0','1024x768x24','-ac','-nolisten','tcp'])
    host=connect(':91')
    launch('nested-vnc',['Xtigervnc',':92','-geometry','640x480','-depth','24',
                         '-SecurityTypes','None','-localhost','yes','-rfbport','5992',
                         '-ac','-nolisten','tcp'])
    nested=connect(':92')
    launch('controller-xvfb',['Xvfb',':93','-screen','0','1280x960x24','-ac','-nolisten','tcp'])
    controller=connect(':93')
    launch('controller-wm',['openbox'],client_env)
    root=host.screen().root
    font=host.open_font('cursor')
    arrow=font.create_glyph_cursor(font,Xcursorfont.left_ptr,Xcursorfont.left_ptr+1,
                                   (0,0,0),(65535,65535,65535))
    root.change_attributes(background_pixel=0x52708a,cursor=arrow)
    root.clear_area()
    # A visible host label makes the remote video path identifiable.
    label=root.create_window(15,15,990,60,0,host.screen().root_depth,
                              X.InputOutput,X.CopyFromParent,background_pixel=0xffffff)
    label.map()
    host.sync()
    gc=label.create_gc(foreground=0x000000,background=0xffffff)
    label.draw_text(gc,12,30,'RustDesk #16703 - real Flutter GUI / X11 / TigerVNC validation')
    nr=nested.screen().root
    nr.change_attributes(background_pixel=0x335d3a)
    nr.clear_area()
    window=nr.create_window(50,50,500,350,0,nested.screen().root_depth,
                            X.InputOutput,X.CopyFromParent,background_pixel=0xdddddd)
    window.set_wm_name('Nested application hides cursor')
    pixmap=nr.create_pixmap(1,1,1)
    pgc=pixmap.create_gc(foreground=0)
    pixmap.fill_rectangle(pgc,0,0,1,1)
    blank=pixmap.create_cursor(pixmap,(0,0,0),(0,0,0),0,0)
    window.change_attributes(cursor=blank)
    window.map()
    nested.sync()
    wgc=window.create_gc(foreground=0x000000,background=0xdddddd)
    window.draw_text(wgc,20,30,'Move here: nested app intentionally hides its X cursor')
    nested.sync()
    launch('vnc-viewer',['vncviewer','-SecurityTypes','None','-Shared','-AlwaysCursor=0',
                         '-geometry','640x480+200+100','127.0.0.1::5992'],host_env)
    xtest.fake_input(host,X.MotionNotify,x=50,y=80)
    host.sync()
    controller.screen().root.change_attributes(background_pixel=0x242424)
    controller.screen().root.clear_area()
    controller.sync()
    (OUT/'ready.json').write_text(json.dumps({'ready':True}))
    seen=None
    while True:
        path=OUT/'command.json'
        if path.exists():
            command=json.loads(path.read_text())
            if command['id']!=seen:
                seen=command['id']
                try:
                    action=command['action']
                    result={}
                    if action=='server':
                        stop('server')
                        mode=command['mode']
                        launch('server',[str(ART/('cursor-network-'+mode)),'server'],
                               dict(host_env,XDG_CONFIG_HOME=str(OUT/('config-server-'+mode))))
                    elif action=='client':
                        stop('client')
                        launch('client',['dbus-run-session','--',
                               str(OUT/'client/usr/share/rustdesk/rustdesk'),
                               '--connect','127.0.0.1:21183','--password','local-only-16703-validation'],client_env)
                    elif action=='move':
                        target=controller if command.get('display',':93')==':93' else host
                        xtest.fake_input(target,X.MotionNotify,x=command['x'],y=command['y'])
                        target.sync()
                    elif action=='click':
                        xtest.fake_input(controller,X.MotionNotify,x=command['x'],y=command['y'])
                        xtest.fake_input(controller,X.ButtonPress,1)
                        xtest.fake_input(controller,X.ButtonRelease,1)
                        controller.sync()
                    elif action=='capture':
                        name=command['name']
                        subprocess.run(['ffmpeg','-y','-loglevel','error','-f','x11grab','-draw_mouse','1',
                                        '-video_size','1280x960','-i',':93','-frames:v','1',str(OUT/(name+'.png'))],check=True)
                        result={'cursor':cursor_probe(':93',name),
                                'host_cursor':cursor_probe(':91',name),
                                'host_pointer':{k:v for k,v in root.query_pointer()._data.items() if k in ['root_x','root_y']}}
                    elif action=='stop-client': stop('client')
                    elif action=='status':
                        result={'processes':{name:{'pid':p.pid,'returncode':p.poll()} for name,p in processes.items()},
                                'windows':[{'id':w.id,'name':w.get_wm_name()} for w in controller.screen().root.query_tree().children]}
                    elif action=='stop':
                        (OUT/'response.json').write_text(json.dumps({'id':seen,'ok':True}))
                        break
                    else: raise ValueError('unknown action '+action)
                    (OUT/'response.json').write_text(json.dumps({'id':seen,'ok':True,**result}))
                except Exception as error:
                    (OUT/'response.json').write_text(json.dumps({'id':seen,'ok':False,'error':repr(error)}))
        time.sleep(.05)
finally:
    for name in list(processes)[::-1]: stop(name)
