"""Owner-local macOS USB device discovery. No device data, identifiers or secrets in status output.

This is a limited onboarding diagnostic, not a replacement for CoreDevice,
Xcode, Remote XPC or a signed WebDriverAgent.
"""
from __future__ import annotations

import json
import os
import plistlib
import re
import socket
import struct
import subprocess
import time
import sys
from contextlib import contextmanager
from pathlib import Path

MAX_PACKET = 2 * 1024 * 1024
SOCKET_PATH = "/var/run/usbmuxd"


def _read_packet(sock, n):
    if type(n) is not int or not 0 < n <= MAX_PACKET:
        raise ValueError("Invalid packet")
    data = bytearray()
    while len(data) < n:
        part = sock.recv(n-len(data))
        if not part:
            raise EOFError("Device disconnected")
        data.extend(part)
    return bytes(data)


@contextmanager
def _connect():
    if sys.platform != "darwin":
        raise OSError("macOS required")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(4)
        sock.connect(SOCKET_PATH)
        yield sock


def _mux(sock, message, **args):
    raw=plistlib.dumps(dict(MessageType=message, ClientVersionString="RDC owner diagnostic",
                            ProgName="RDC", kLibUSBMuxVersion=3, **args))
    sock.sendall(struct.pack("<IIII",len(raw)+16,1,8,1)+raw)
    size,version,kind,tag=struct.unpack("<IIII",_read_packet(sock,16))
    if version != 1 or kind != 8 or tag != 1:
        raise ValueError("Unexpected USB response")
    result=plistlib.loads(_read_packet(sock,size-16))
    if not isinstance(result,dict):
        raise ValueError("Unexpected USB response")
    return result


def _lockdown(sock, request, **args):
    raw=plistlib.dumps(dict(Request=request,Label="RDC owner diagnostic",**args))
    sock.sendall(struct.pack(">I",len(raw))+raw)
    size=struct.unpack(">I",_read_packet(sock,4))[0]
    result=plistlib.loads(_read_packet(sock,size))
    if not isinstance(result,dict):
        raise ValueError("Unexpected device response")
    return result


def _devices():
    with _connect() as sock:
        devices=_mux(sock,"ListDevices").get("DeviceList")
    if not isinstance(devices,list) or len(devices)>64:
        raise ValueError("Unexpected device list")
    return devices


def _choose_usb(devices, udid):
    selected=[]
    for device in devices:
        if not isinstance(device,dict):
            continue
        props=device.get("Properties")
        if not isinstance(props,dict) or props.get("ConnectionType")!="USB":
            continue
        serial=props.get("SerialNumber")
        if not isinstance(serial,str) or not re.fullmatch(r"[A-Za-z0-9-]{8,128}",serial):
            continue
        if type(device.get("DeviceID")) is not int:
            continue
        if udid is None or serial==udid:
            selected.append(device)
    return selected[0] if len(selected)==1 else None


def _probe(device):
    result={"device_service":False,"trust_accepted":False}
    serial=device["Properties"]["SerialNumber"]
    with _connect() as sock:
        response=_mux(sock,"ReadPairRecord",PairRecordID=serial)
    raw=response.get("PairRecordData")
    # Never write or expose the existing host pairing record.
    pair=plistlib.loads(raw) if isinstance(raw,bytes) and len(raw)<=MAX_PACKET else {}
    if not isinstance(pair,dict):
        pair={}
    with _connect() as sock:
        response=_mux(sock,"Connect",DeviceID=device["DeviceID"],PortNumber=socket.htons(62078))
        if response.get("Number")!=0:
            return result
        result["device_service"]=_lockdown(sock,"QueryType").get("Type")=="com.apple.mobile.lockdown"
        if not result["device_service"]:
            return result
        for key,output in (("ProductType","product_type"),("ProductVersion","ios_version")):
            value=_lockdown(sock,"GetValue",Key=key).get("Value")
            if isinstance(value,str) and re.fullmatch(r"[A-Za-z0-9.,_-]{1,40}",value):
                result[output]=value
        if all(isinstance(pair.get(k),str) and 1<=len(pair[k])<=256 for k in ("HostID","SystemBUID")):
            response=_lockdown(sock,"StartSession",HostID=pair["HostID"],SystemBUID=pair["SystemBUID"])
            result["trust_accepted"]=bool(response.get("SessionID")) and not response.get("Error")
            # A positive StartSession is evidence of accepted existing pairing,
            # not proof that TLS or developer services have been established.
            # Close this diagnostic socket immediately; no persistent session.
            if result["trust_accepted"] and response.get("EnableSessionSSL") is False:
                _lockdown(sock,"StopSession",SessionID=response["SessionID"])
    return result


def usb_check(udid=None):
    base={"usb_connected":False,"device_service":False,"trust_accepted":False}
    try:
        device=_choose_usb(_devices(),udid)
        if device is None:
            return {**base,"status":"no_unique_usb_device"}
        return {**base,"usb_connected":True,**_probe(device),"status":"diagnostic_only"}
    except (OSError,EOFError,ValueError,TypeError,KeyError,plistlib.InvalidFileException,struct.error):
        return {**base,"status":"unavailable"}


def write_profile(output,alias,udid=None):
    """Require a unique explicitly connected trusted USB phone. Never change live config."""
    device=_choose_usb(_devices(),udid)
    if device is None:
        raise ValueError("No unique USB device selected")
    evidence=_probe(device)
    if evidence.get("trust_accepted") is not True:
        raise ValueError("Existing pairing was not accepted")
    from .mobile_install import make_profile
    fragment={"mobile_profiles":make_profile(alias,"ios",device["Properties"]["SerialNumber"],"com.apple.Preferences")}
    target=Path(output).expanduser().absolute()
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"w") as stream:
        json.dump(fragment,stream,indent=2)
        stream.write("\n")
    return target


def _ideviceinfo():
    # Owner-installed Homebrew binary only; do not accept an agent path.
    if sys.platform != "darwin":
        return None
    for path in ("/opt/homebrew/bin/ideviceinfo", "/usr/local/bin/ideviceinfo"):
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def device_metrics(udid):
    """Bounded read-only USB diagnostics for an exact owner-selected iOS profile."""
    if not isinstance(udid,str) or not re.fullmatch(r"[A-Za-z0-9-]{8,128}",udid):
        return {"metrics_status":"invalid_target"}
    evidence=usb_check(udid)
    if evidence.get("trust_accepted") is not True:
        return {**evidence,"metrics_status":"trust_required"}
    binary=_ideviceinfo()
    if binary is None:
        return {**evidence,"metrics_status":"library_required"}
    fields=(
        ("com.apple.disk_usage","TotalDiskCapacity","storage_total_bytes",2**53-1),
        ("com.apple.disk_usage","TotalDataAvailable","storage_available_bytes",2**53-1),
        ("com.apple.disk_usage","TotalDataCapacity","storage_data_capacity_bytes",2**53-1),
        ("com.apple.mobile.battery","BatteryCurrentCapacity","battery_percent",100),
        ("com.apple.mobile.battery","BatteryIsCharging","charging",None),
        ("com.apple.security.mac.amfi","DeveloperModeStatus","developer_mode",None),
    )
    metrics={}
    deadline=time.monotonic()+10
    for domain,key,name,maximum in fields:
        remaining=deadline-time.monotonic()
        if remaining<=0:
            break
        try:
            result=subprocess.run([binary,"-u",udid,"-q",domain,"-k",key],
                stdin=subprocess.DEVNULL,capture_output=True,text=True,
                timeout=min(remaining,4),env={"PATH":"/usr/bin:/bin","LC_ALL":"C"})
        except (OSError,subprocess.SubprocessError,UnicodeError):
            continue
        if result.returncode!=0 or len(result.stdout)>128:
            continue
        value=result.stdout.strip()
        if maximum is None:
            if value in ("true","false"):
                metrics[name]=value=="true"
        elif re.fullmatch(r"[0-9]{1,16}",value) and 0<=int(value)<=maximum:
            metrics[name]=int(value)
    if "storage_available_bytes" in metrics and "storage_data_capacity_bytes" in metrics and metrics["storage_available_bytes"]>metrics["storage_data_capacity_bytes"]:
        metrics.pop("storage_available_bytes")
    return {**evidence,**metrics,"metrics_status":"complete" if len(metrics)==len(fields) else "partial" if metrics else "unavailable"}


def _pmd_python():
    path=Path.home()/".local/share/uv/tools/pymobiledevice3/bin/python"
    return str(path) if path.is_file() and os.access(path,os.X_OK) else None


def _go_ios_binary():
    path=Path.home()/".local/share/rdc/tools/go-ios/ios"
    return str(path) if path.is_file() and os.access(path,os.X_OK) else None


def _safe_json_command(argv,timeout=10,limit=65536):
    """Only fixed local tool arguments; never return raw output or stderr."""
    try:
        proc=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,
            text=True,timeout=timeout,env={"PATH":"/usr/bin:/bin","HOME":str(Path.home()),"LC_ALL":"C"})
        if proc.returncode or len(proc.stdout)>limit:
            return {}
        obj=json.loads(proc.stdout)
        return obj if isinstance(obj,dict) else {}
    except (OSError,ValueError,subprocess.SubprocessError,UnicodeError):
        return {}


def _clean_metrics(obj):
    metrics={}
    for k in ("storage_total_bytes","storage_available_bytes","storage_data_capacity_bytes","battery_percent"):
        v=obj.get(k)
        if type(v) is int and 0<=v<=(100 if k=="battery_percent" else 2**53-1):
            metrics[k]=v
    for k in ("charging","developer_mode"):
        if type(obj.get(k)) is bool:
            metrics[k]=obj[k]
    if metrics.get("storage_available_bytes",0)>metrics.get("storage_data_capacity_bytes",2**53-1):
        metrics.pop("storage_available_bytes",None)
    return metrics


def preferred_device_metrics(udid,backend="auto"):
    """Select a vetted read-only backend, with safe fallback on incomplete diagnostics."""
    if backend not in ("auto","pymobiledevice3","libimobiledevice","go-ios"):
        return {"metrics_status":"invalid_backend"}
    if not isinstance(udid,str) or not re.fullmatch(r"[A-Za-z0-9-]{8,128}",udid):
        return {"metrics_status":"invalid_target"}
    evidence=usb_check(udid)
    if evidence.get("trust_accepted") is not True:
        return {**evidence,"metrics_status":"trust_required"}
    if backend=="go-ios":
        binary=_go_ios_binary()
        if not binary:
            return {**evidence,"backend":"go-ios","metrics_status":"library_required"}
        obj=_safe_json_command([binary,"info","lockdown","--udid="+udid],limit=262144)
        verified=bool(obj.get("ProductVersion")==evidence.get("ios_version") and
                      obj.get("ProductType")==evidence.get("product_type") and
                      evidence.get("ios_version") and evidence.get("product_type"))
        return {**evidence,"backend":"go-ios","backend_verified":verified,
                "metrics_status":"identity_only" if verified else "unavailable"}
    primary={}
    if backend in ("auto","pymobiledevice3"):
        python=_pmd_python()
        if python:
            primary=_clean_metrics(_safe_json_command([python,"-I",str(Path(__file__).with_name("ios_pmd_worker.py")),udid]))
            if len(primary)==6 or backend=="pymobiledevice3":
                return {**evidence,**primary,"backend":"pymobiledevice3",
                        "metrics_status":"complete" if len(primary)==6 else "partial" if primary else "unavailable"}
        elif backend=="pymobiledevice3":
            return {**evidence,"backend":"pymobiledevice3","metrics_status":"library_required"}
    fallback=device_metrics(udid)
    if fallback.get("trust_accepted") is not True:
        return fallback
    if primary and fallback.get("metrics_status")!="complete":
        merged=_clean_metrics({**primary,**_clean_metrics(fallback)})
        return {**evidence,**merged,"backend":"pymobiledevice3+libimobiledevice",
                "metrics_status":"complete" if len(merged)==6 else "partial"}
    return {**fallback,"backend":"libimobiledevice"}


def developer_preflight(udid):
    """Readiness only; never mount a DDI or expose RemoteXPC endpoints."""
    if not isinstance(udid,str) or not re.fullmatch(r"[A-Za-z0-9-]{8,128}",udid):
        return {"developer_status":"invalid_target","remote_xpc_connected":False}
    evidence=usb_check(udid)
    result={**evidence,"remote_xpc_connected":False,"native_ui_verified":False}
    if evidence.get("trust_accepted") is not True:
        return {**result,"developer_status":"trust_required"}
    python=_pmd_python()
    if not python:
        return {**result,"developer_status":"library_required"}
    obj=_safe_json_command([python,"-I",str(Path(__file__).with_name("ios_developer_probe.py")),udid],timeout=24)
    for field in ("developer_mode","developer_image_mounted"):
        if type(obj.get(field)) is bool:
            result[field]=obj[field]
    status=obj.get("developer_status")
    if status not in ("unavailable","trust_required","developer_mode_required","identity_mismatch","tunnel_verified"):
        status="unavailable"
    count=obj.get("remote_service_count")
    if status=="tunnel_verified" and obj.get("remote_xpc_connected") is True and result.get("developer_mode") is True and type(count) is int and 0<=count<=4096:
        result["remote_xpc_connected"]=True
        result["remote_service_count"]=count
        for field in ("application_service_advertised","device_info_service_advertised",
                      "debug_service_advertised","instruments_service_advertised","image_service_advertised"):
            if type(obj.get(field)) is bool:
                result[field]=obj[field]
    elif status=="tunnel_verified":
        status="unavailable"
    return {**result,"developer_status":status}
