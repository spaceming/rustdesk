import hashlib
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont

out=Path('/work/16703-gui')
events=[json.loads(line) for line in (out/'gui-results.jsonl').read_text().splitlines()]
captures={e['request']['name']:e['response'] for e in events
          if e['request']['action']=='capture' and e['response']['ok']}
labels=['baseline-before','baseline-inside','baseline-after','baseline-start-hidden',
        'fixed-before','fixed-inside','fixed-after','fixed-start-hidden']
checks={}
for label in labels:
    record=captures[label]
    hidden='inside' in label or 'start-hidden' in label
    should_be_visible=label.startswith('fixed') or not hidden
    checks[label]=(record['cursor']['visible_pixels']>0)==should_be_visible
    if hidden:
        checks[label+'-host-really-hidden']=record['host_cursor']['visible_pixels']==0
summary={'checks':checks,'captures':{key:captures[key] for key in labels},
         'controller':{'url':'https://github.com/rustdesk/rustdesk/releases/download/1.5.3/rustdesk-1.5.3-x86_64.deb',
                       'sha256':hashlib.file_digest((out/'rustdesk-1.5.3-x86_64.deb').open('rb'),'sha256').hexdigest()},
         'videos':{}}
for mode in ['baseline','fixed']:
    data=subprocess.check_output(['ffprobe','-v','error','-show_entries',
        'format=duration:stream=codec_name,width,height,r_frame_rate','-of','json',
        str(out/(mode+'-visual.mp4'))],text=True)
    summary['videos'][mode]=json.loads(data)
(out/'gui-summary.json').write_text(json.dumps(summary,indent=2))
assert all(checks.values()),checks

# Derived comparison: enlarged crops of raw x11grab screenshots, with captions.
# Cursor pixels come from the real display capture; none are added here.
panels=[('baseline-inside','Baseline: pointer disappears'),
        ('fixed-inside','Patched: pointer remains visible'),
        ('baseline-start-hidden','Baseline: connect while hidden'),
        ('fixed-start-hidden','Patched: default dot is visible')]
canvas=Image.new('RGB',(760,760),'#f5f5f5')
draw=ImageDraw.Draw(canvas)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
for i,(name,caption) in enumerate(panels):
    x=(i%2)*380
    y=(i//2)*380
    draw.text((x+15,y+16),caption,fill='#111111',font=font)
    crop=Image.open(out/(name+'.png')).crop((488,370,588,470)).resize((300,300),Image.Resampling.NEAREST)
    canvas.paste(crop,(x+40,y+55))
canvas.save(out/'gui-comparison.png')
print(json.dumps(checks,indent=2))
