"""Isolated direct iOS application readiness and launch; no install/remove.

Only the exact already-trusted USB device and owner-selected installed bundle
are addressed. No arbitrary launch arguments, environment, signals, screen
capture, UI input, app termination, new pairing, or network listeners.
"""
import asyncio
import json
import logging
import re
import sys

FEATURE = "com.apple.coredevice.feature.launchapplication"


async def run(udid, bundle, action):
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.installation_proxy import InstallationProxyService
    from pymobiledevice3.services.mobile_image_mounter import MobileImageMounterService
    from pymobiledevice3.remote.tunnel_service import CoreDeviceTunnelProxy
    from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel, TunnelProvider
    from pymobiledevice3.remote.core_device.app_service import AppServiceService
    from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
    from pymobiledevice3.services.dvt.instruments.process_control import ProcessControl

    async def checked_usb():
        client = await create_using_usbmux(serial=udid, autopair=False,
                    connection_type="USB", pair_timeout=0)
        try:
            if (not client.paired or not client.session_id
                    or not isinstance(client.udid,str) or client.udid.casefold()!=udid.casefold()):
                raise RuntimeError("trust_required")
            if await client.get_value("com.apple.security.mac.amfi","DeveloperModeStatus") is not True:
                raise RuntimeError("developer_mode_required")
            async with MobileImageMounterService(client) as mounter:
                if await mounter.is_image_mounted("Personalized") is not True:
                    raise RuntimeError("developer_image_required")
            async with InstallationProxyService(client) as apps:
                result = await apps.lookup({"BundleIDs":[bundle],
                           "ReturnAttributes":["CFBundleIdentifier"]})
                if (not isinstance(result,dict) or not isinstance(result.get(bundle),dict)
                        or result[bundle].get("CFBundleIdentifier") != bundle):
                    raise RuntimeError("application_not_installed")
            return client
        except BaseException:
            await client.close()
            raise

    async def provider():
        client=await checked_usb()
        try:
            return TunnelProvider(await CoreDeviceTunnelProxy.create(client),client)
        except BaseException:
            await client.close()
            raise

    sent=False
    acknowledged=False
    running=False
    try:
        async with UserspaceRsdTunnel(serial=udid,autopair=False,
                remotepairing_fallback=False,provider_factory=provider) as rsd:
            if not isinstance(rsd.udid,str) or rsd.udid.casefold()!=udid.casefold():
                return {"status":"identity_mismatch"}
            # Require positive advertised support before permitting a mutation.
            if FEATURE not in rsd.get_service_features(AppServiceService.SERVICE_NAME):
                return {"status":"application_service_required"}
            if action=="prepare":
                return {"status":"ready","app_installed":True}
            async with AppServiceService(rsd) as apps:
                sent=True
                reply=await apps.launch_application(bundle,kill_existing=False,
                         start_suspended=False,arguments=[],environment={})
                acknowledged=isinstance(reply,(dict,list))
            if acknowledged:
                try:
                    async with DvtProvider(rsd) as dvt, ProcessControl(dvt) as process:
                        pid=await asyncio.wait_for(
                            process.process_identifier_for_bundle_identifier(bundle),timeout=5)
                        # DTX can return an int subclass. Do not expose the PID.
                        running=isinstance(pid,int) and not isinstance(pid,bool) and 0<pid<2**31
                except Exception:
                    pass
        # Success requires tunnel cleanup and a valid acknowledgment.
        if acknowledged:
            return {"status":"running_verified" if running else "launch_acknowledged",
                    "launch_acknowledged":True,"process_running":running}
        return {"status":"outcome_unknown" if sent else "unavailable"}
    except Exception as exc:
        if sent:
            return {"status":"outcome_unknown"}
        code=exc.args[0] if type(exc) is RuntimeError and len(exc.args)==1 else None
        if code in ("trust_required","developer_mode_required","developer_image_required","application_not_installed"):
            return {"status":code}
        return {"status":"unavailable"}


if __name__=="__main__":
    try:
        from loguru import logger
        logger.remove()
        logging.disable(logging.CRITICAL)
        if (len(sys.argv)!=4 or sys.argv[3] not in ("prepare","launch")
                or not re.fullmatch(r"[A-Za-z0-9-]{8,128}",sys.argv[1])
                or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)+",sys.argv[2])
                or len(sys.argv[2])>256):
            raise ValueError
        print(json.dumps(asyncio.run(asyncio.wait_for(run(*sys.argv[1:]),timeout=20))))
    except Exception:
        print('{"status":"outcome_unknown"}' if len(sys.argv)==4 and sys.argv[3]=="launch" else '{"status":"unavailable"}')
