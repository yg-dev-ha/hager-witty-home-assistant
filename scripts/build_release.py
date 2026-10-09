"""Build the manual-install ZIP without credentials, caches or repository files."""
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / 'custom_components/hager_witty'
version = json.loads((INTEGRATION / 'manifest.json').read_text())['version']
output = ROOT / 'dist' / f'hager-witty-v{version}.zip'
output.parent.mkdir(exist_ok=True)
files = [p for p in INTEGRATION.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
files += [ROOT / name for name in ('README.md', 'README.fr.md', 'LICENSE', 'CHANGELOG.md')]
files += sorted((ROOT / 'docs/assets').glob('*.svg'))
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for path in sorted(files):
        archive.write(path, path.relative_to(ROOT))
print(output)
