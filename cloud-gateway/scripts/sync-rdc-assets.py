"""Copy public RDC catalog, embedded view and original brand asset into this gateway.

Run with the RDC virtual environment's Python. No device profile, credential,
browser state, owner configuration, or private workspace content is copied.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--rdc-source', required=True, type=Path)
args = parser.parse_args()
source = args.rdc_source.resolve()
project = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(source))
from rdc.config import Settings
from rdc.engine import Engine

scratch = project / '.rdc-export'
scratch.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=scratch) as temporary:
    root = Path(temporary)
    engine = Engine(Settings(state_dir=root/'state', roots=[root]))
    try:
        catalog = engine.catalog()
    finally:
        engine.close()
scratch.rmdir()
html = (source/'rdc/embedded/preview.html').read_text(encoding='utf-8')
logo = source/'rdc/assets/rdc-logo.png'
payload = {'catalog': catalog, 'resourceHtml': html,
           'iconDataUri': 'data:image/png;base64,' + base64.b64encode(logo.read_bytes()).decode()}
(project/'lib/rdc-assets.json').write_text(json.dumps(payload, separators=(',',':')), encoding='utf-8')
(project/'public').mkdir(exist_ok=True)
shutil.copyfile(logo, project/'public/rdc-logo.png')
print(json.dumps({'tools':len(catalog),'html_bytes':len(html.encode()),'logo_bytes':logo.stat().st_size}))
