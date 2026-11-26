from dataclasses import dataclass, field, asdict, fields
import json
import os
from pathlib import Path
import tempfile

from .errors import RDCError


@dataclass
class Settings:
    state_dir: Path
    roots: list[Path]
    access_mode: str = 'workspace'
    approval_mode: str = 'review'
    allow_exec: bool = False
    desktop_mode: str = 'disabled'
    browser_backend: str = 'playwright'
    webdriver_url: str | None = None
    webdriver_capabilities: dict | None = None
    adb_serial: str | None = None
    mobile_profiles: dict = field(default_factory=dict)
    ios_mirroring_enabled: bool = False
    ios_coredevice_launch_enabled: bool = False
    ios_direct_terminal_enabled: bool = False
    max_output_bytes: int = 10 * 1024 * 1024
    max_read_bytes: int = 262144
    job_timeout: float = 3600
    max_concurrent_jobs: int = 8
    allowed_origins: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.state_dir = Path(self.state_dir).expanduser().absolute()
        self.roots = [Path(p).expanduser().resolve() for p in self.roots]
        choices = {'access_mode': ('workspace', 'full-host'), 'approval_mode': ('review', 'trusted'),
                   'desktop_mode': ('disabled', 'shared', 'isolated'),
                   'browser_backend': ('playwright', 'webdriver', 'disabled')}
        for key, options in choices.items():
            if getattr(self, key) not in options:
                raise RDCError('invalid_config', f'{key} must be one of {options}')
        if not self.roots:
            raise RDCError('invalid_config', 'At least one working root is required.')
        if type(self.ios_direct_terminal_enabled) is not bool:
            raise RDCError('invalid_config', 'ios_direct_terminal_enabled must be true or false.')
        if type(self.ios_coredevice_launch_enabled) is not bool:
            raise RDCError('invalid_config', 'ios_coredevice_launch_enabled must be true or false.')
        if type(self.ios_mirroring_enabled) is not bool:
            raise RDCError('invalid_config', 'ios_mirroring_enabled must be true or false.')
        if type(self.allow_exec) is not bool:
            raise RDCError('invalid_config', 'allow_exec must be true or false.')
        for key, low, high in [('max_output_bytes', 1024, 1024**3), ('max_read_bytes', 1024, 4*1024**2),
                               ('max_concurrent_jobs', 1, 64)]:
            value = getattr(self, key)
            if type(value) is not int or not low <= value <= high:
                raise RDCError('invalid_config', f'{key} must be between {low} and {high}.')
        if isinstance(self.job_timeout, bool) or not isinstance(self.job_timeout, (int,float)) or not 0 < self.job_timeout <= 604800:
            raise RDCError('invalid_config', 'job_timeout must be greater than zero and at most seven days.')
        if not isinstance(self.allowed_origins, list) or not all(isinstance(x,str) for x in self.allowed_origins):
            raise RDCError('invalid_config', 'allowed_origins must be a list of origins.')
        if self.webdriver_capabilities is not None and not isinstance(self.webdriver_capabilities, dict):
            raise RDCError('invalid_config', 'webdriver_capabilities must be an object.')
        from .mobile import validate_mobile_profiles
        validate_mobile_profiles(self.mobile_profiles)

    @classmethod
    def load(cls, path):
        try:
            data = json.loads(Path(path).read_text())
            if not isinstance(data, dict) or set(data) - {f.name for f in fields(cls)}:
                raise ValueError('Unknown configuration field or invalid object')
            return cls(**data)
        except (ValueError, TypeError, OSError) as exc:
            raise RDCError('invalid_config', f'Cannot load settings: {exc}') from exc

    def public(self):
        data = asdict(self)
        data['state_dir'] = str(self.state_dir)
        data['roots'] = [str(p) for p in self.roots]
        # Remote driver options can contain credentials. Only the owner config file contains them.
        data.pop('webdriver_url')
        data.pop('webdriver_capabilities')
        data.pop('mobile_profiles')
        data['webdriver_configured'] = self.webdriver_url is not None
        return data

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        data['state_dir'] = str(self.state_dir)
        data['roots'] = [str(p) for p in self.roots]
        fd, temporary = tempfile.mkstemp(prefix='.rdc-config-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w') as output:
                json.dump(data, output, indent=2)
                output.write('\n')
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

