"""Keep verification screenshots outside a frozen candidate when configured."""
import os
from pathlib import Path


def artifact_path(filename):
    source = Path(__file__).resolve().parents[1]
    configured = os.environ.get('RDC_TEST_ARTIFACT_DIR')
    directory = Path(configured).expanduser().resolve() if configured else source/'test-results'
    if configured and (directory == source or source in directory.parents):
        raise ValueError('RDC_TEST_ARTIFACT_DIR must be outside the source tree.')
    directory.mkdir(parents=True, exist_ok=True)
    return directory/filename
