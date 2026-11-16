"""Build the looping 4K and Full HD previews from the recorded screenshot deck."""
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
ffmpeg = shutil.which('ffmpeg')
if not ffmpeg:
    raise SystemExit('Install ffmpeg before generating the previews.')
shots = sorted((root / 'screenshots').glob('*.png'))
durations = [2, 3, 3, 3, 4, 4, 4, 4, 3]
if len(shots) != len(durations):
    raise SystemExit('Expected the nine recorded screenshots.')
with tempfile.TemporaryDirectory(prefix='northline-preview-') as directory:
    directory = Path(directory)
    lines = []
    for index, (shot, duration) in enumerate(zip(shots, durations)):
        # Simple local names keep the concat manifest independent of path quoting.
        name = f'{index:02}.png'
        (directory / name).symlink_to(shot)
        lines.extend([f"file '{name}'", f'duration {duration}'])
    manifest = directory / 'frames.txt'
    manifest.write_text('\n'.join(lines) + '\n')
    for label, scale in [('4K', ''), ('1080p', 'scale=1920:1080:flags=lanczos,')]:
        filters = (f'[0:v]{scale}split[a][b];'
                   '[a]palettegen=max_colors=256:stats_mode=full[p];'
                   '[b][p]paletteuse=dither=bayer:bayer_scale=3')
        subprocess.run([
            ffmpeg, '-hide_banner', '-loglevel', 'warning', '-y',
            '-f', 'concat', '-safe', '0', '-i', str(manifest),
            '-filter_complex', filters, '-fps_mode', 'vfr',
            '-loop', '0', '-final_delay', '300',
            str(root / f'Northline-Preview-{label}.gif'),
        ], check=True)
