"""Detached supervisor. Output and completion outlive the calling MCP session."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from .store import Store


def terminate_tree(process):
    if os.name == 'nt':
        # taskkill is available on supported Windows desktop editions. Do not kill
        # arbitrary supplied PIDs: this is the child just created by this worker.
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        # Descendants can outlive a quickly exiting parent. Always signal the group.
        time.sleep(.2)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run(state_dir, job_id):
    store = Store(state_dir)
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT * FROM jobs WHERE id=? AND status='queued'", (job_id,)).fetchone()
        if not row:
            return
        if row['cancel_requested']:
            db.execute("UPDATE jobs SET status='cancelled', finished_at=? WHERE id=?", (time.time(),job_id))
            return
        spec = json.loads(row['spec'])
        db.execute("UPDATE jobs SET status='running',started_at=?,heartbeat=?,worker_pid=? WHERE id=?", (time.time(),time.time(),os.getpid(),job_id))
    directory = Path(state_dir)/'jobs'
    output_path = directory/f'{job_id}.output'
    process = None
    final = 'failed'
    exit_code = None
    error = None
    stats = {'bytes':0,'truncated':False,'capture_errors':[],'input_errors':[]}
    reader_done = threading.Event()
    pipe_read_failed = threading.Event()
    writer_done = threading.Event()
    stopped = threading.Event()
    timed_out = False
    try:
        options = {'start_new_session':True} if os.name != 'nt' else {'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP}
        process = subprocess.Popen(spec['argv'], cwd=spec['cwd'], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0, **options)
        with store.connection() as db:
            db.execute('UPDATE jobs SET pid=? WHERE id=?', (process.pid,job_id))

        def capture():
            destination = None

            def capture_failed(exc):
                stats['capture_errors'].append(f'{type(exc).__name__}: {exc}')
                stats['truncated'] = True

            def close_destination():
                nonlocal destination
                if destination is not None:
                    try:
                        destination.close()
                    except Exception as exc:
                        capture_failed(exc)
                    finally:
                        destination = None

            try:
                try:
                    destination = open(output_path, 'wb', buffering=0)
                except Exception as exc:
                    capture_failed(exc)
                while True:
                    try:
                        chunk = process.stdout.read(65536)
                    except Exception as exc:
                        pipe_read_failed.set()
                        capture_failed(exc)
                        break
                    if not chunk:
                        break
                    room = max(0,spec['max_output_bytes']-stats['bytes'])
                    kept = chunk[:room]
                    if kept and destination is not None:
                        try:
                            # Raw files may make partial writes. Count only bytes
                            # accepted, and never retry indefinitely without progress.
                            remaining = memoryview(kept)
                            while remaining:
                                written = destination.write(remaining)
                                if written is None or written <= 0 or written > len(remaining):
                                    raise OSError('Output file write made no valid progress.')
                                stats['bytes'] += written
                                remaining = remaining[written:]
                        except Exception as exc:
                            capture_failed(exc)
                            close_destination()
                    if len(chunk)>room:
                        stats['truncated'] = True
                    # Keep draining after a file failure so the child cannot
                    # deadlock on its output pipe. Memory stays bounded per chunk.
            except Exception as exc:
                capture_failed(exc)
            finally:
                close_destination()
                reader_done.set()

        def deliver_input():
            try:
                while not stopped.is_set():
                    with store.connection() as db:
                        entries = db.execute('SELECT * FROM job_input WHERE job_id=? AND delivered=0 ORDER BY seq LIMIT 32', (job_id,)).fetchall()
                    for entry in entries:
                        if entry['text']:
                            # Unbuffered pipes can accept only part of a write,
                            # including when a signal interrupts a blocked write.
                            # Advance only over accepted bytes before acknowledging.
                            remaining = memoryview(entry['text'].encode('utf-8'))
                            while remaining:
                                written = process.stdin.write(remaining)
                                if written is None or written <= 0 or written > len(remaining):
                                    raise OSError('Input pipe write made no valid progress.')
                                remaining = remaining[written:]
                            process.stdin.flush()
                        if entry['close_input']:
                            process.stdin.close()
                        with store.connection() as db:
                            db.execute('UPDATE job_input SET delivered=1 WHERE seq=?', (entry['seq'],))
                        if entry['close_input']:
                            return
                    stopped.wait(.04)
            except Exception as exc:
                # A partial input may already have caused effects. Leave its
                # record unacknowledged, stop this stream, and never replay it.
                stats['input_errors'].append(f'{type(exc).__name__}: {exc}')
                try:
                    process.stdin.close()
                except (OSError, ValueError):
                    pass
                try:
                    with store.connection() as db:
                        db.execute('UPDATE jobs SET stdin_closed=1 WHERE id=?', (job_id,))
                except Exception:
                    pass
            finally:
                writer_done.set()

        threading.Thread(target=capture, daemon=True).start()
        threading.Thread(target=deliver_input, daemon=True).start()
        start = time.monotonic()
        while process.poll() is None or not reader_done.is_set():
            with store.connection() as db:
                state = db.execute('SELECT cancel_requested,status FROM jobs WHERE id=?', (job_id,)).fetchone()
                db.execute('UPDATE jobs SET heartbeat=?,bytes_written=?,truncated=? WHERE id=?',
                           (time.time(),stats['bytes'],int(stats['truncated']),job_id))
            if state['cancel_requested'] or state['status']=='interrupted':
                final = 'cancelled' if state['cancel_requested'] else 'interrupted'
                terminate_tree(process)
                break
            if time.monotonic()-start >= spec['timeout']:
                final = 'timed_out'
                timed_out = True
                terminate_tree(process)
                break
            if pipe_read_failed.is_set() and process.poll() is None:
                # A pipe read failure cannot be drained. Stop the owned child
                # instead of leaving it blocked until the command timeout.
                terminate_tree(process)
                break
            # Wake promptly when an EOF-first child actually exits.
            # An unconditional sleep here adds up to 40 ms after child
            # completion. A bounded wait returns immediately on real exit,
            # while still checking cancellation/timeout at least every 40 ms.
            if reader_done.is_set():
                try:
                    process.wait(timeout=.04)
                except subprocess.TimeoutExpired:
                    pass
            else:
                reader_done.wait(.04)
        exit_code = process.wait(timeout=10)
        if final not in ('cancelled','timed_out','interrupted'):
            final = 'completed' if exit_code == 0 else 'failed'
        reader_done.wait(3)
        if not reader_done.is_set():
            # A child inherited the output handle. Do not wait forever or pretend
            # the stream is complete; terminate remaining owned descendants.
            terminate_tree(process)
            reader_done.wait(2)
            if not reader_done.is_set():
                error = 'Output pipe did not close after process-tree termination.'
                final = 'interrupted'
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        if process is not None:
            try:
                terminate_tree(process)
            except Exception:
                pass
            # A backend can signal the child and then fail. Reap independently
            # of that attempt, while keeping cleanup bounded if it is still live.
            try:
                exit_code = process.wait(timeout=10)
            except Exception:
                if exit_code is None:
                    error += ' Owned child exit could not be confirmed after cleanup.'
    finally:
        stopped.set()
        writer_done.wait(.2)
        if process is not None:
            for stream in (process.stdin, process.stdout):
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass
        if stats['capture_errors']:
            capture_error = ('Output capture failed; output is incomplete. '
                             'The command may have finished successfully. ' +
                             '; '.join(stats['capture_errors']))
            error = f'{error} {capture_error}' if error else capture_error
            if final == 'completed':
                final = 'failed'
        if stats['input_errors']:
            input_error = ('Input delivery failed; queued input may be incomplete and was not replayed. ' +
                           '; '.join(stats['input_errors']))
            error = f'{error} {input_error}' if error else input_error
            if final == 'completed':
                final = 'failed'
        with store.connection() as db:
            db.execute('UPDATE jobs SET status=?,finished_at=?,heartbeat=?,exit_code=?,bytes_written=?,truncated=?,error=? WHERE id=?',
                       (final,time.time(),time.time(),exit_code,stats['bytes'],int(stats['truncated']),error,job_id))


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2])
