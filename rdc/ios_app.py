"""Explicit opt-in, single-use, owner-reviewed native iOS app launch."""
import re
import time
import uuid
from pathlib import Path

from .errors import RDCError
from .ios_usb import _pmd_python, _safe_json_command, usb_check

SAFE_FAILURES = {"unavailable","trust_required","developer_mode_required",
    "developer_image_required","application_not_installed","identity_mismatch",
    "application_service_required","library_required"}


def _dispatch(udid, bundle, action):
    if usb_check(udid).get("trust_accepted") is not True:
        return {"status":"trust_required"}
    python=_pmd_python()
    if not python:
        return {"status":"library_required"}
    payload=_safe_json_command([python,"-I",str(Path(__file__).with_name("ios_app_worker.py")),
                      udid,bundle,action],timeout=25)
    status=payload.get("status")
    if status in SAFE_FAILURES:
        return {"status":status}
    if action=="prepare" and status=="ready" and payload.get("app_installed") is True:
        return {"status":"ready","app_installed":True}
    if action=="launch" and status in ("running_verified","launch_acknowledged"):
        running=payload.get("process_running")
        if (payload.get("launch_acknowledged") is True and type(running) is bool
                and running==(status=="running_verified")):
            return {"status":status,"launch_acknowledged":True,"process_running":running}
    return {"status":"outcome_unknown" if action=="launch" else "unavailable"}


class IOSAppLaunch:
    def __init__(self,settings,profiles):
        self.enabled=getattr(settings,"ios_coredevice_launch_enabled",False) is True
        self.profiles=profiles
        self.ticket=None

    def invalidate(self):
        self.ticket=None

    def _target(self,profile):
        if not self.enabled:
            raise RDCError("ios_app_launch_disabled","Owner opt-in is required for direct iOS application launch.")
        config=self.profiles.get(profile)
        if not config or config["platformName"]!="iOS":
            raise RDCError("profile_not_found","The exact iOS profile is not configured.")
        caps=config["capabilities"]
        udid=caps.get("appium:udid")
        bundle=caps.get("appium:bundleId")
        if (not isinstance(udid,str) or not re.fullmatch(r"[A-Za-z0-9-]{8,128}",udid)
                or not isinstance(bundle,str) or len(bundle)>256
                or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)+",bundle)):
            raise RDCError("invalid_config","The owner must choose an exact USB device and installed bundle.")
        return (profile,udid,bundle)

    def prepare(self,profile):
        self.invalidate()
        target=self._target(profile)
        result=_dispatch(*target[1:],"prepare")
        output={"profile":profile,**result,"owner_approval_required":True,
                "native_ui_verified":False}
        if result.get("status")=="ready":
            token=str(uuid.uuid4())
            self.ticket=(token,time.monotonic()+120,target)
            output["observation_id"]=token
        return output

    def launch(self,profile,observation_id):
        target=self._target(profile)
        ticket=self.ticket
        if not ticket or ticket[0]!=observation_id or ticket[1]<time.monotonic() or ticket[2]!=target:
            raise RDCError("stale_observation","Prepare this exact installed application again.")
        self.invalidate()
        result=_dispatch(*target[1:],"launch")
        if result.get("status")=="outcome_unknown":
            raise RDCError("ios_app_outcome_unknown","The app launch may have occurred. Do not replay it.")
        if result.get("status") not in ("running_verified","launch_acknowledged"):
            raise RDCError("ios_app_launch_unavailable","The exact app launch could not proceed.")
        return {"profile":profile,**result,"native_ui_verified":False,
                "foreground_verified":False}
