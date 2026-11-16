from pathlib import Path
import subprocess,json,shutil,tempfile
root=Path(__file__).resolve().parent.parent
p=root/'production/qwen-audio';render=Path(tempfile.mkdtemp(prefix='northline-audio-export-'));render.mkdir(exist_ok=True)
ffmpeg=shutil.which('ffmpeg')
chapters=json.loads((p/'chapters.json').read_text())
for c in chapters:
 audio=p/'shots'/f"shot_{c['shot']:02}"/'audio_en.wav';video=render/(c['id']+'.mp4');length=c['end']-c['start']
 subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-loop','1','-framerate','30','-i',str(root/'screenshots'/(c['id']+'.png')),'-i',str(audio),'-vf',f'scale=1920:1080:flags=lanczos,setsar=1,fade=t=in:d=0.25,fade=t=out:st={length-.3}:d=0.3,format=yuv420p','-af','loudnorm=I=-16:TP=-1.5:LRA=7,adelay=400:all=1,apad','-t',str(length),'-c:v','libx264','-preset','fast','-crf','19','-threads','4','-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-movflags','+faststart',str(video)],check=True)
 print('Encoded',c['id'],flush=True)
(render/'concat.txt').write_text(''.join("file '"+c['id']+".mp4'\n" for c in chapters))
subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(render/'concat.txt'),'-c','copy',str(render/'combined.mp4')],check=True)
meta=';FFMETADATA1\ntitle=Northline — Knowledge Workspace Demo\ncomment=Real app screenshots with local Qwen3-TTS Ryan narration. Fictional company materials.\n'
for c in chapters:meta+=f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={round(c['start']*1000)}\nEND={round(c['end']*1000)}\ntitle={c['id'][3:].replace('-',' ').title()}\n"
(render/'chapters.ffmeta').write_text(meta)
subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(render/'combined.mp4'),'-i',str(p/'subtitles_en.srt'),'-i',str(render/'chapters.ffmeta'),'-map','0:v','-map','0:a','-map','1:s','-map_metadata','2','-map_chapters','2','-c:v','copy','-c:a','copy','-c:s','mov_text','-metadata:s:s:0','language=eng','-movflags','+faststart',str(render/'Northline-Demo-1080p.mp4')],check=True)
subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(render/'Northline-Demo-1080p.mp4'),'-map','0:a','-c:a','libmp3lame','-q:a','2',str(render/'Northline-Narration-Ryan.mp3')],check=True)
print('FINISHED',chapters[-1]['end'],'seconds',flush=True)

for name in ["Northline-Demo-1080p.mp4", "Northline-Narration-Ryan.mp3"]: shutil.copy2(render/name,root/name)
shutil.copy2(p/"subtitles_en.srt",root/"Northline-Demo.en.srt")
