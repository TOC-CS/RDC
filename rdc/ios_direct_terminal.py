"""Explicit, owner-approved developer transport for the RDC sandbox only.

The private local journal fences each request before copying or launching.
A lost response is recoverable only by reading the exact result; no input
retry, generic shell, remote service listener, or app selection by the AI.
"""
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
import uuid

from .errors import RDCError

COMPANION='org.tocministries.rdc.mobile'
VERSION='0.1.3'
BUILD='4'
MAX_REQUESTS=256
MAX_RECEIPT_BYTES=32768
UUID_PATTERN=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
DIGEST_PATTERN=r'^[0-9a-f]{64}$'

def valid_id(value):
    return isinstance(value,str) and re.fullmatch(UUID_PATTERN,value) is not None

def _error(code):
    messages={
      'direct_terminal_disabled':'Owner opt-in is required for the direct iOS sandbox terminal.',
      'direct_terminal_unavailable':'Exact trusted developer connection or compatible companion build is unavailable.',
      'direct_terminal_conflict':'Request identity conflicts with the original configured device or command.',
      'direct_terminal_unknown':'An earlier request on this device has an unknown outcome. Recover its exact receipt without replay.',
      'direct_terminal_journal_full':'Direct terminal journal capacity reached. Owner review is required; no records are silently removed.',
      'direct_terminal_recovery_required':'Direct terminal journal cannot be verified. Owner inspection is required.',
      'invalid_arguments':'Use a canonical request UUID and one bounded sandbox command.',
      'mobile_app_scope_required':'Select an exact owner-configured iOS RDC companion profile.',
      'direct_terminal_not_found':'This request was not admitted by this worker.',
    }
    raise RDCError(code,messages[code])

class DeveloperTransport:
    """Fixed Apple developer-service invocations; never exports inventory."""
    @staticmethod
    def _call(udid,args,timeout=12):
        if sys.platform!='darwin': raise OSError('developer transport unavailable')
        with tempfile.TemporaryDirectory(prefix='rdc-direct-control-') as tmp:
            path=Path(tmp)/'receipt.json'
            proc=subprocess.run(['/usr/bin/xcrun','devicectl','device',*args,
                '--device',udid,'--timeout',str(timeout),'--json-output',str(path)],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=timeout+4)
            if proc.returncode!=0:return None
            if not path.is_file() or path.stat().st_size>16*1024*1024:return None
            return json.loads(path.read_text())
    def preflight(self,udid):
        if sys.platform!='darwin':return False
        from .ios_usb import usb_check
        if usb_check(udid).get('trust_accepted') is not True:return False
        data=self._call(udid,['info','apps','--include-all-apps'],15)
        if not isinstance(data,dict):return False
        apps=data.get('result',{}).get('apps',[])
        found=[a for a in apps if isinstance(a,dict) and a.get('bundleIdentifier')==COMPANION]
        return len(found)==1 and str(found[0].get('version'))==VERSION and str(found[0].get('bundleVersion'))==BUILD
    def submit(self,udid,payload):
        ident=payload['request_id']
        with tempfile.TemporaryDirectory(prefix='rdc-direct-request-') as tmp:
            path=Path(tmp)/('rdc-request-'+ident+'.json')
            with path.open('x') as f:
                os.fchmod(f.fileno(),0o600)
                json.dump(payload,f,ensure_ascii=False,separators=(',',':'))
                f.flush();os.fsync(f.fileno())
            if self._call(udid,['copy','to','--source',str(path),'--destination','Documents/'+path.name,
                    '--domain-type','appDataContainer','--domain-identifier',COMPANION]) is None:
                raise OSError('request copy outcome unknown')
            # Explicitly launch this companion only. The durable host and
            # companion request claims both precede execution; never replay.
            proc=subprocess.run(['/usr/bin/xcrun','devicectl','device','process','launch',
                '--device',udid,'--terminate-existing','--timeout','15',COMPANION,
                '--','--rdc-direct-terminal',ident],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=19)
            if proc.returncode!=0:raise OSError('launch outcome unknown')
    def read(self,udid,ident):
        with tempfile.TemporaryDirectory(prefix='rdc-direct-result-') as tmp:
            for i in range(3):
                path=Path(tmp)/('result-'+str(i)+'.json')
                result=self._call(udid,['copy','from','--source','Documents/rdc-result-'+ident+'.json',
                    '--destination',str(path),'--domain-type','appDataContainer','--domain-identifier',COMPANION],10)
                if result is not None and path.is_file() and 0<path.stat().st_size<=MAX_RECEIPT_BYTES:
                    try:return json.loads(path.read_text())
                    except (OSError,ValueError):pass
                if i<2:time.sleep(.2*(i+1))
        return None

class DirectTerminal:
    companion = COMPANION
    def __init__(self,settings,profiles,transport=None):
        self.enabled=getattr(settings,'ios_direct_terminal_enabled',False) is True
        self.profiles=profiles
        self.root=Path(getattr(settings,'state_dir','.'))/'direct-terminal-v1'
        self.transport=transport if transport is not None else DeveloperTransport()

    def _target(self,profile):
        if not self.enabled:_error('direct_terminal_disabled')
        p=self.profiles.get(profile)
        caps=p.get('capabilities',{}) if isinstance(p,dict) else {}
        udid=caps.get('appium:udid')
        if (not p or p.get('platformName')!='iOS' or p.get('automationName')!='XCUITest'
                or caps.get('appium:bundleId')!=self.companion or not isinstance(udid,str)
                or not re.fullmatch(r'[A-Za-z0-9-]{8,128}',udid)):
            _error('mobile_app_scope_required')
        device=hashlib.sha256(('ios:'+udid.casefold()).encode()).hexdigest()
        binding=hashlib.sha256(json.dumps([device,self.companion,profile],separators=(',',':')).encode()).hexdigest()
        return udid,device,binding

    @contextmanager
    def _locked(self):
        try:import fcntl
        except ImportError:_error('direct_terminal_unavailable')
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        info=self.root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode & 0o077:
            _error('direct_terminal_recovery_required')
        fd=os.open(self.root/'journal.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:
                _error('direct_terminal_recovery_required')
            fcntl.flock(fd,fcntl.LOCK_EX)
            yield
        finally:os.close(fd)

    def _records(self):
        records={}
        for path in self.root.glob('*.json'):
            info=path.lstat()
            if (not valid_id(path.stem) or not stat.S_ISREG(info.st_mode)
                    or info.st_uid!=os.getuid() or info.st_mode&0o077 or not 0<info.st_size<=4096):
                _error('direct_terminal_recovery_required')
            try:r=json.loads(path.read_text())
            except (OSError,ValueError):_error('direct_terminal_recovery_required')
            fields={'request_id','device','binding','command_sha256','phase'}
            digests=('device','binding','command_sha256')
            if isinstance(r,dict) and r.get('phase')=='verified':
                fields.add('receipt_sha256')
                digests+=('receipt_sha256',)
            if (not isinstance(r,dict) or set(r)!=fields
                    or r.get('request_id')!=path.stem or r.get('phase') not in ('pending','unknown','verified')
                    or any(not isinstance(r.get(k),str) or not re.fullmatch(DIGEST_PATTERN,r[k])
                           for k in digests)):
                _error('direct_terminal_recovery_required')
            records[path.stem]=r
        return records

    def _save(self,record):
        path=self.root/(record['request_id']+'.json')
        fd,temporary=tempfile.mkstemp(prefix='.journal-',dir=self.root)
        try:
            with os.fdopen(fd,'w') as f:
                os.fchmod(f.fileno(),0o600);json.dump(record,f,separators=(',',':'))
                f.flush();os.fsync(f.fileno())
            os.replace(temporary,path)
            d=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(d)
            finally:os.close(d)
        finally:
            if os.path.exists(temporary):os.unlink(temporary)

    @staticmethod
    def _base(record):
        return {'request_id':record['request_id'],'execution_location':'mobile_device',
                'command_route':'mobile_sandbox_direct','command_sha256':record['command_sha256'],
                'execution_verified':False,'executed':False,'submission_status':'unknown',
                'next_step':'Recover the exact result. Never resubmit an uncertain command.'}

    def _read(self,udid,record):
        base=self._base(record)
        try:
            receipt=self.transport.read(udid,record['request_id'])
            if (not isinstance(receipt,dict) or set(receipt)!={'schema','request_id','run_id','command_sha256','exit_code','device_elapsed_ms','output','execution_location'}
                    or type(receipt['schema']) is not int or receipt['schema']!=1
                    or receipt['request_id']!=record['request_id'] or not valid_id(receipt['run_id'])
                    or receipt['command_sha256']!=record['command_sha256']
                    or receipt['execution_location']!='mobile_device'
                    or type(receipt['exit_code']) is not int or receipt['exit_code'] not in (0,1)
                    or type(receipt['device_elapsed_ms']) not in (float,int)
                    or not math.isfinite(receipt['device_elapsed_ms']) or not 0<=receipt['device_elapsed_ms']<30000
                    or not isinstance(receipt['output'],str) or len(receipt['output'].encode('utf-8'))>4096
                    or any(unicodedata.category(c)=='Cc' and c not in ('\n','\t') for c in receipt['output'])):
                raise ValueError()
        except Exception:
            if record['phase']!='verified':
                record['phase']='unknown';self._save(record)
            return base
        receipt_digest=hashlib.sha256(json.dumps(receipt,sort_keys=True,
            ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()
        if record['phase']=='verified':
            if record['receipt_sha256']!=receipt_digest:
                _error('direct_terminal_recovery_required')
        else:
            record['phase']='verified'
            record['receipt_sha256']=receipt_digest
            self._save(record)
        base.pop('next_step')
        return base | {'execution_verified':True,'executed':True,'submission_status':'acknowledged',
                       **{k:receipt[k] for k in ('run_id','exit_code','device_elapsed_ms','output')}}

    def execute(self,profile,request_id,command):
        started=time.perf_counter()
        udid,device,binding=self._target(profile)
        try:
            encoded=command.encode('utf-8') if isinstance(command,str) else b''
        except UnicodeError:
            _error('invalid_arguments')
        if (not valid_id(request_id) or not isinstance(command,str) or not command.strip()
                or len(encoded)>4000 or any(unicodedata.category(c)=='Cc' for c in command)):
            _error('invalid_arguments')
        digest=hashlib.sha256(command.encode()).hexdigest()
        payload={'schema':1,'request_id':request_id,'command':command,'command_sha256':digest}
        if len(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode())>8192:_error('invalid_arguments')
        with self._locked():
            records=self._records()
            if request_id in records:
                record=records[request_id]
                if record['binding']!=binding or record['command_sha256']!=digest:_error('direct_terminal_conflict')
                return self._read(udid,record) | {'command_total_ms':round((time.perf_counter()-started)*1000,3)}
            if any(r['device']==device and r['phase']!='verified' for r in records.values()):
                _error('direct_terminal_unknown')
            if len(records)>=MAX_REQUESTS:_error('direct_terminal_journal_full')
            try:ready=self.transport.preflight(udid)
            except Exception:ready=False
            if ready is not True:_error('direct_terminal_unavailable')
            record={'request_id':request_id,'device':device,'binding':binding,'command_sha256':digest,'phase':'pending'}
            self._save(record)
            try:self.transport.submit(udid,payload)
            except Exception:
                record['phase']='unknown';self._save(record)
                return self._base(record) | {'command_total_ms':round((time.perf_counter()-started)*1000,3)}
            return self._read(udid,record) | {'command_total_ms':round((time.perf_counter()-started)*1000,3)}

    def recover(self,profile,request_id):
        udid,device,binding=self._target(profile)
        if not valid_id(request_id):_error('invalid_arguments')
        with self._locked():
            record=self._records().get(request_id)
            if record is None:_error('direct_terminal_not_found')
            if record['binding']!=binding:_error('direct_terminal_conflict')
            return self._read(udid,record)
