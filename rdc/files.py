from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import stat
import tempfile

from .errors import RDCError


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class Files:
    def __init__(self, settings):
        self.settings = settings

    def resolve(self, value, directory=False):
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.settings.roots[0] / path
        path = Path(os.path.abspath(path))
        resolved = path.resolve()
        private = self.settings.state_dir.resolve()
        if resolved == private or private in resolved.parents:
            raise RDCError('path_denied', 'RDC private state is not available through file or working-directory tools.')
        if self.settings.access_mode == 'workspace':
            root = next((root for root in self.settings.roots if resolved == root or root in resolved.parents),None)
            if root is None:
                raise RDCError('path_denied', 'Path is outside the configured working roots.')
            for part in (path, *path.parents):
                # An OS alias above an explicitly granted root (macOS /var)
                # is legitimate. Check symlinks inside the granted tree only.
                if part.resolve() == root:
                    break
                if part.is_symlink():
                    raise RDCError('path_denied', 'Symbolic links are not followed in workspace mode.')
        if directory and not resolved.is_dir():
            raise RDCError('not_directory', 'Working directory does not exist or is not a directory.')
        return resolved

    def _read_bytes(self, path, limit=None):
        with self._open_regular(path) as source:
            return source.read((limit if limit is not None else self.settings.max_read_bytes) + 1)

    @staticmethod
    @contextmanager
    def _open_regular(path):
        # O_NONBLOCK prevents FIFO open from hanging before the regular-file
        # check. Verify the opened descriptor, not an earlier raceable stat.
        descriptor = os.open(path,os.O_RDONLY | getattr(os,'O_NONBLOCK',0) | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_BINARY',0))
        with os.fdopen(descriptor,'rb') as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise RDCError('not_regular_file','Only regular files can be read.')
            yield source

    def _image_location(self, file_path, path, *, initial=False):
        """Recheck the granted path and the identity of every resolved parent."""
        from .file_images import _fingerprint
        try:
            if self.resolve(file_path) != path:
                raise RDCError('conflict', 'Image location changed during inspection. Read it again.')
            parents = []
            for parent in path.parents:
                info = parent.stat(follow_symlinks=False)
                if not stat.S_ISDIR(info.st_mode):
                    raise RDCError('conflict', 'Image location changed during inspection. Read it again.')
                parents.append((info.st_dev, info.st_ino))
            return tuple(parents), _fingerprint(path.stat(follow_symlinks=False))
        except OSError:
            if initial:
                raise
            raise RDCError('conflict', 'Image location changed during inspection. Read it again.') from None

    def read(self, file_path, offset=0, limit=None, mode='auto', max_edge=1280):
        from .file_images import _fingerprint, identify_image, read_image
        if mode not in ('auto','text','image'):
            raise RDCError('invalid_arguments', 'Read mode must be auto, text or image.')
        if type(max_edge) is not int or not 320 <= max_edge <= 1600:
            raise RDCError('invalid_arguments', 'Image max_edge must be between 320 and 1600.')
        if mode=='image' and (offset or limit is not None):
            raise RDCError('invalid_arguments', 'Images must be read without byte pagination.')
        path = self.resolve(file_path)
        location = self._image_location(file_path, path, initial=True) if mode != 'text' else None
        with self._open_regular(path) as source:
            info = os.fstat(source.fileno())
            def image_guard():
                if (self._image_location(file_path, path) != location
                        or _fingerprint(info) != location[1]
                        or _fingerprint(os.fstat(source.fileno())) != _fingerprint(info)):
                    raise RDCError('conflict', 'Image location changed during inspection. Read it again.')
            if location is not None:
                image_guard()
            detected = None if mode=='text' else identify_image(source.read(16))
            source.seek(0)
            if mode=='image' or detected is not None:
                if offset or limit is not None:
                    raise RDCError('image_read_required', 'Read this image individually without byte pagination.')
                return read_image(source, path, info, detected, max_edge=max_edge,
                                  output_limit=self.settings.max_read_bytes, guard=image_guard)
            limit = min(limit or self.settings.max_read_bytes, self.settings.max_read_bytes)
            # Hash without loading an entire large file into memory.
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
            source.seek(offset)
            data = source.read(limit)
        return {'file_path':str(path), 'text':data.decode('utf-8', errors='replace'), 'sha256':digest,
                'offset':offset, 'next_offset':offset+len(data), 'size':info.st_size,
                'truncated':offset+len(data)<info.st_size, 'encoding':'utf-8', 'offset_unit':'bytes'}

    def list(self, path='.', limit=200):
        directory = self.resolve(path, directory=True)
        entries = []
        truncated = False
        with os.scandir(directory) as iterator:
            for entry in iterator:
                if Path(entry.path).resolve() == self.settings.state_dir.resolve():
                    continue
                if len(entries) == limit:
                    truncated = True
                    break
                entries.append({'name':entry.name, 'type':'symlink' if entry.is_symlink() else
                                'directory' if entry.is_dir(follow_symlinks=False) else 'file',
                                'size':entry.stat(follow_symlinks=False).st_size})
        return {'path':str(directory), 'entries':sorted(entries,key=lambda x:x['name']), 'truncated':truncated}

    @contextmanager
    def lock(self, path):
        directory = self.settings.state_dir / 'locks'
        directory.mkdir(exist_ok=True, mode=0o700)
        lockpath = directory / (sha256(str(path).encode()) + '.lock')
        with open(lockpath, 'a+b') as guard:
            if os.name == 'nt':
                import msvcrt
                if guard.tell() == 0:
                    guard.write(b'\0')
                    guard.flush()
                guard.seek(0)
                msvcrt.locking(guard.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(guard, fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == 'nt':
                    guard.seek(0)
                    msvcrt.locking(guard.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(guard, fcntl.LOCK_UN)

    def _current(self, path):
        if not path.exists():
            return None, None
        data = self._read_bytes(path)
        if len(data) > self.settings.max_read_bytes:
            raise RDCError('file_too_large', 'Use a background job for files larger than the configured edit limit.')
        return data, sha256(data)

    @staticmethod
    def _check_precondition(actual, expected):
        if actual != expected:
            raise RDCError('conflict', 'The file differs from the expected version. Read it again before editing.',
                           {'actual_sha256':actual})

    def write(self, file_path, content, expected_sha256=None):
        path = self.resolve(file_path)
        data = content.encode('utf-8')
        if len(data) > self.settings.max_read_bytes:
            raise RDCError('input_too_large', 'Content exceeds the configured write limit.')
        with self.lock(path):
            _, actual = self._current(path)
            self._check_precondition(actual, expected_sha256)
            return self._replace(path, data)

    def _replace(self, path, data):
        fd, temporary = tempfile.mkstemp(prefix='.rdc-write-', dir=path.parent)
        try:
            mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
            with os.fdopen(fd, 'wb') as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temporary, mode)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return {'file_path':str(path), 'bytes_written':len(data), 'sha256':sha256(data)}

    def edit(self, file_path, old_text, new_text, expected_sha256,
             expected_count=1, scoped_root=None):
        path = self.resolve(file_path)
        if scoped_root is not None:
            root = self.resolve(scoped_root, directory=True)
            # Check the actual resolved target inside the edit operation.
            # A source path may have turned into a symlink after an earlier
            # multi-edit admission check; never edit its external destination.
            if path == root or root not in path.parents:
                raise RDCError('path_denied',
                    'A coding edit must stay beneath its selected project.')
        with self.lock(path):
            data, actual = self._current(path)
            self._check_precondition(actual, expected_sha256)
            if data is None:
                raise RDCError('not_found', 'File does not exist.')
            try:
                text = data.decode('utf-8')
            except UnicodeDecodeError as exc:
                raise RDCError('invalid_encoding', 'Exact edits require UTF-8 text.') from exc
            count = text.count(old_text)
            if count != expected_count:
                raise RDCError('match_count', 'The exact text occurrence count differs from expected_count.', {'actual_count':count})
            output = text.replace(old_text, new_text).encode('utf-8')
            if len(output) > self.settings.max_read_bytes:
                raise RDCError('input_too_large', 'Edited content exceeds the configured write limit.')
            return {**self._replace(path, output), 'replacements':count}

    def search(self, path, query, limit=100, max_files=1000, exclude_dirs=()):
        # Only the coding-context tool opts into source-only pruning.
        # Generic file search retains its original all-directory behavior.
        directory = self.resolve(path, directory=True)
        matches = []
        scanned = 0
        skipped = 0
        for parent, dirs, filenames in os.walk(directory, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in exclude_dirs
                             and not (Path(parent)/d).is_symlink()
                             and (Path(parent)/d).resolve() != self.settings.state_dir.resolve())
            for name in sorted(filenames):
                candidate = Path(parent)/name
                if candidate.is_symlink():
                    continue
                if scanned >= max_files:
                    return {'matches':matches, 'truncated':True, 'files_scanned':scanned, 'files_skipped':skipped}
                scanned += 1
                try:
                    # Directory entries can be replaced with symlinks after
                    # os.walk enumerates them. Keep each actual opened file
                    # inside the selected search subtree, even in full-host mode.
                    resolved = self.resolve(str(candidate))
                    if resolved != directory and directory not in resolved.parents:
                        skipped += 1
                        continue
                    data = self._read_bytes(resolved)
                    if len(data) > self.settings.max_read_bytes or b'\0' in data:
                        skipped += 1
                        continue
                    for line_number, line in enumerate(data.decode('utf-8').splitlines(), 1):
                        if query in line:
                            if len(matches) == limit:
                                return {'matches':matches, 'truncated':True, 'files_scanned':scanned, 'files_skipped':skipped}
                            matches.append({'file_path':str(candidate), 'line':line_number, 'text':line[:2000]})
                except (OSError, UnicodeDecodeError, RDCError):
                    skipped += 1
        return {'matches':matches, 'truncated':False, 'files_scanned':scanned, 'files_skipped':skipped}

