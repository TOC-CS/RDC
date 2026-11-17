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
# Preserve the original brand logo for the Site and native RDC UI. Reusing
# the full-size data URI inflated the MCP initialize response by >1 MB.
# This checked-in thumbnail provides deterministic cross-platform builds.
mcp_icon = source/'rdc/assets/rdc-icon-192.png'
icon_bytes = mcp_icon.read_bytes()
if (not icon_bytes.startswith(bytes.fromhex('89504e470d0a1a0a'))
        or len(icon_bytes) > 60_000
        or int.from_bytes(icon_bytes[16:20], 'big') != 192
        or int.from_bytes(icon_bytes[20:24], 'big') != 192):
    raise RuntimeError('MCP icon must be the checked-in 192x192 PNG <= 60000 bytes')
payload = {'catalog': catalog, 'resourceHtml': html,
           'iconDataUri': 'data:image/png;base64,' + base64.b64encode(icon_bytes).decode()}
(project/'lib/rdc-assets.json').write_text(json.dumps(payload, separators=(',',':')), encoding='utf-8')
(project/'public').mkdir(exist_ok=True)
shutil.copyfile(logo, project/'public/rdc-logo.png')
shutil.copyfile(mcp_icon, project/'public/rdc-mcp-icon.png')
print(json.dumps({'tools':len(catalog),'html_bytes':len(html.encode()),
                  'logo_bytes':logo.stat().st_size,'mcp_icon_bytes':len(icon_bytes)}))
