"""Opt-in Apple iPhone Mirroring menu navigation.

Only the Apple-owned application and its three fixed navigation commands are
addressed. No screen images, phone accessibility contents, coordinates supplied
by an agent, text entry, clipboard, or arbitrary keyboard shortcuts.
"""
from __future__ import annotations

import subprocess
import sys
import time
import uuid

from .errors import RDCError

ACTIONS = {"home":"Home Screen", "app_switcher":"App Switcher", "spotlight":"Spotlight"}
NOTICE = ("Apple selects the mirrored phone. The owner must verify the intended "
          "phone in iPhone Mirroring. Phone contents are never captured by this adapter.")
OBSERVE_SCRIPT = '''
tell application "System Events"
 set candidates to every application process whose bundle identifier is "com.apple.ScreenContinuity"
 if (count of candidates) is not 1 then return "unavailable"
 tell item 1 of candidates
  if (count of windows) is not 1 then return "unavailable"
  if (name of front window as text) is not "iPhone Mirroring" then return "unavailable"
  set {w, h} to size of front window
  set {x, y} to position of front window
  set pidValue to unix id
  set flags to {}
  tell menu "View" of menu bar 1
   repeat with labelText in {"Home Screen", "App Switcher", "Spotlight"}
    try
     set end of flags to enabled of menu item (labelText as text)
    on error
     set end of flags to false
    end try
   end repeat
  end tell
  return (pidValue as text) & tab & (x as text) & tab & (y as text) & tab & (w as text) & tab & (h as text) & tab & (item 1 of flags as text) & tab & (item 2 of flags as text) & tab & (item 3 of flags as text)
 end tell
end tell
'''
NAVIGATE_SCRIPT = '''
on run argv
 if (count of argv) is not 6 then return "stale"
 set expectedPID to item 1 of argv as integer
 set expectedX to item 2 of argv as integer
 set expectedY to item 3 of argv as integer
 set expectedW to item 4 of argv as integer
 set expectedH to item 5 of argv as integer
 set commandName to item 6 of argv
 if commandName is not in {"Home Screen", "App Switcher", "Spotlight"} then return "stale"
 tell application "System Events"
  set candidates to every application process whose bundle identifier is "com.apple.ScreenContinuity"
  if (count of candidates) is not 1 then return "stale"
  tell item 1 of candidates
   if unix id is not expectedPID or (count of windows) is not 1 then return "stale"
   if (name of front window as text) is not "iPhone Mirroring" then return "stale"
   set {w, h} to size of front window
   set {x, y} to position of front window
   if x is not expectedX or y is not expectedY or w is not expectedW or h is not expectedH then return "stale"
   tell menu "View" of menu bar 1
    if not (enabled of menu item commandName) then return "stale"
    -- Invoke the exact menu item, never a global key or mouse event.
    perform action "AXPress" of menu item commandName
   end tell
   return "dispatched"
  end tell
 end tell
end run
'''

def _script(source, args=()):
    if sys.platform!="darwin":
        return None
    try:
        p=subprocess.run(["/usr/bin/osascript","-e",source,*args],
            stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=8)
        if p.returncode==0 and len(p.stdout)<=1024:
            return p.stdout.strip()
    except (OSError,subprocess.SubprocessError,UnicodeError):
        pass
    return None


def _process_start(pid):
    try:
        p=subprocess.run(["/bin/ps","-p",str(pid),"-o","lstart="],
            stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=2)
        value=p.stdout.strip()
        if p.returncode==0 and 1<=len(value)<=80:
            return value
    except (OSError,subprocess.SubprocessError,UnicodeError):
        pass
    return None


def _window():
    raw=_script(OBSERVE_SCRIPT)
    if not raw:
        return None
    values=raw.split("\t")
    if len(values)!=8 or any(v not in ("true","false") for v in values[5:]):
        return None
    try:
        bounds=tuple(int(v) for v in values[:5])
    except ValueError:
        return None
    pid,x,y,w,h=bounds
    if not (0<pid<2**31 and abs(x)<100000 and abs(y)<100000 and 1<=w<=16384 and 1<=h<=16384):
        return None
    started=_process_start(pid)
    if not started:
        return None
    return {"identity":bounds+(started,),"actions":tuple(k for k,v in zip(ACTIONS,values[5:]) if v=="true")}


class Mirroring:
    def __init__(self,settings):
        self.enabled=(getattr(settings,"ios_mirroring_enabled",False) is True and
                      getattr(settings,"desktop_mode","disabled")!="disabled")
        self.observation=None

    def _allowed(self):
        if not self.enabled:
            raise RDCError("mirror_disabled","Owner opt-in and a desktop grant are required.")

    def observe(self):
        self._allowed()
        self.observation=None
        window=_window()
        if not window:
            raise RDCError("mirror_unavailable","The exact Apple Mirroring window is unavailable.")
        token=str(uuid.uuid4())
        self.observation=(token,time.monotonic()+120,window)
        return {"observation_id":token,"window_available":True,
                "actions":list(window["actions"]),"width":window["identity"][3],
                "height":window["identity"][4],"privacy_notice":NOTICE,
                "phone_identity_verified":False,"screen_capture":False,
                "owner_approval_required":True}

    def navigate(self,observation_id,action):
        self._allowed()
        previous=self.observation
        if not previous or previous[0]!=observation_id or previous[1]<time.monotonic():
            raise RDCError("stale_observation","Observe the selected mirroring window again.")
        # Consume before any possible mutation; unknown outcomes cannot replay.
        self.observation=None
        if action not in ACTIONS or action not in previous[2]["actions"]:
            raise RDCError("invalid_arguments","The selected menu command is unavailable.")
        current=_window()
        if (not current or current["identity"]!=previous[2]["identity"] or
                action not in current["actions"]):
            raise RDCError("stale_observation","The exact mirroring window or menu changed.")
        args=[str(v) for v in current["identity"][:5]]+[ACTIONS[action]]
        answer=_script(NAVIGATE_SCRIPT,args)
        if answer=="stale":
            raise RDCError("stale_observation","The exact mirroring window or menu changed.")
        if answer!="dispatched":
            raise RDCError("mirror_outcome_unknown","Menu dispatch could not be confirmed. Do not replay.")
        return {"action":action,"status":"dispatched","verification_required":True,
                "privacy_notice":NOTICE}
