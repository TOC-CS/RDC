"""Owner-only Android USB onboarding and bounded read-only device status.

Require a unique USB transport and an already-authorized device. Do not
automatically pair, connect over TCP, accept debugging prompts, launch apps,
change permissions, or return private ADB device identifiers.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

_SERIAL = re.compile(r"[A-Za-z0-9_.-]{1,128}")
_STATES = {"device","unauthorized","offline","recovery","sideload","bootloader"}


def _adb_binary():
    home=Path.home()
    if sys.platform=="darwin":
        candidates=(Path("/opt/homebrew/bin/adb"),Path("/usr/local/bin/adb"),
                    home/"Library/Android/sdk/platform-tools/adb")
    elif sys.platform.startswith("linux"):
        candidates=(Path("/usr/bin/adb"),Path("/usr/local/bin/adb"),
                    home/"Android/Sdk/platform-tools/adb")
    elif os.name=="nt":
        candidates=(home/"AppData/Local/Android/Sdk/platform-tools/adb.exe",)
    else:
        return None
    return next((str(p) for p in candidates if p.is_file() and os.access(p,os.X_OK)),None)


def _run(binary, *args):
    # No agent-selected server, network destination, command, or executable.
    # Retain Windows' system directory for the trusted executable to load.
    env={"PATH":os.defpath,"HOME":str(Path.home()),"LC_ALL":"C"}
    if os.name=="nt":
        for name in ("SystemRoot","WINDIR","USERPROFILE","TEMP","TMP"):
            if name in os.environ:
                env[name]=os.environ[name]
    try:
        proc=subprocess.run([binary,"-H","127.0.0.1","-P","5037",*args],
              stdin=subprocess.DEVNULL,capture_output=True,text=True,
              timeout=8,env=env)
        if proc.returncode==0 and len(proc.stdout)<=65536:
            return proc.stdout
    except (OSError,subprocess.SubprocessError,UnicodeError):
        pass
    return None


def _usb_rows(raw):
    if not isinstance(raw,str) or len(raw)>65536:
        return []
    result=[]
    for line in raw.splitlines():
        fields=line.strip().split()
        if len(fields)<3 or not _SERIAL.fullmatch(fields[0]) or fields[0].startswith("emulator-"):
            continue
        if fields[1] not in _STATES:
            continue
        usb=[f for f in fields[2:] if f.startswith("usb:") and len(f)>4]
        ids=[f[13:] for f in fields[2:] if f.startswith("transport_id:")]
        if len(usb)!=1 or len(ids)!=1 or not re.fullmatch(r"[0-9]{1,10}",ids[0]):
            continue
        result.append({"serial":fields[0],"state":fields[1],"transport_id":ids[0]})
    return result


def _select(serial=None):
    if serial is not None and (not isinstance(serial,str) or not _SERIAL.fullmatch(serial)):
        return None,None,{"status":"invalid_target","usb_connected":False,"trust_accepted":False}
    binary=_adb_binary()
    if not binary:
        return None,None,{"status":"platform_tools_required","usb_connected":False,"trust_accepted":False}
    raw=_run(binary,"devices","-l")
    if raw is None:
        return binary,None,{"status":"unavailable","usb_connected":False,"trust_accepted":False}
    rows=_usb_rows(raw)
    candidates=[row for row in rows if serial is None or row["serial"]==serial]
    if len(candidates)!=1:
        return binary,None,{"status":"no_unique_usb_device","usb_connected":False,"trust_accepted":False}
    row=candidates[0]
    status={"status":row["state"],"usb_connected":True,"trust_accepted":False}
    if row["state"]!="device":
        return binary,row,status
    state=_run(binary,"-t",row["transport_id"],"get-state")
    if state is None or state.strip()!="device":
        return binary,row,{**status,"status":"unavailable"}
    return binary,row,{**status,"status":"ready","trust_accepted":True}


def usb_check(serial=None):
    _,_,evidence=_select(serial)
    return evidence


def write_profile(output,alias,package,activity,serial=None):
    from .mobile_install import make_profile
    binary,row,evidence=_select(serial)
    if not row or evidence.get("trust_accepted") is not True:
        raise ValueError("No uniquely selected authorized USB device")
    fragment={"mobile_profiles":make_profile(alias,"android",row["serial"],package,activity),
              "adb_serial":row["serial"]}
    component=package+"/"+activity
    # Require a positively resolved owner-selected component, never start it.
    resolved=_run(binary,"-t",row["transport_id"],"shell","cmd","package",
                  "resolve-activity","--brief","-n",component)
    if resolved is None:
        raise ValueError("Installed activity could not be verified")
    expected=package+"/"+(package+activity if activity.startswith(".") else activity)
    compact=package+"/"+activity
    if not any(line.strip() in (expected,compact) for line in resolved.splitlines()):
        raise ValueError("Installed activity could not be verified")
    target=Path(output).expanduser().absolute()
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"w") as stream:
        json.dump(fragment,stream,indent=2)
        stream.write("\n")
    return target
