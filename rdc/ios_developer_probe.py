"""Isolated, read-only iOS developer readiness probe over an exact USB device.

No mounting, app installation, new pairing, network pairing, administrator
privileges, exposed listener or screen/content capture. The temporary tunnel
is closed before returning a successful result.
"""
import asyncio
import json
import logging
import math
import re
import sys

SERVICE_GROUPS = {
    "application_service_advertised": ("com.apple.coredevice.appservice",),
    "device_info_service_advertised": ("com.apple.coredevice.deviceinfo",),
    "debug_service_advertised": ("com.apple.debugserver",),
    "instruments_service_advertised": ("com.apple.instruments",),
    "image_service_advertised": ("com.apple.mobile.mobile_image_mounter",),
}


INTERACTION_SERVICES = {
    "touch_service_advertised": "com.apple.coredevice.hid.universalhidservice",
    "hardware_button_service_advertised": "com.apple.coredevice.hid.indigo",
    "accessibility_service_advertised": "com.apple.accessibility.axAuditDaemon.remoteserver.shim.remote",
    "screen_capture_service_advertised": "com.apple.coredevice.screencaptureservice",
}


def primary_display_metadata(info):
    """Return only bounded dimensions and orientation of one actual built-in primary display."""
    if not isinstance(info, dict):
        return {}
    displays = info.get("displays")
    if not isinstance(displays, list) or len(displays) > 64:
        return {}
    rows = [d for d in displays if isinstance(d, dict)
            and d.get("primary") is True and d.get("external") is False]
    if len(rows) != 1:
        return {}
    row = rows[0]
    native = row.get("nativeSize")
    if not isinstance(native, (list, tuple)) or len(native) != 2:
        return {}
    if not all(isinstance(v, (int,float)) and not isinstance(v, bool)
               and math.isfinite(v) and 1 <= v <= 16384 and int(v) == v for v in native):
        return {}
    width,height = map(int,native)
    if width * height > 48000000:
        return {}
    result = {"native_width":width, "native_height":height}
    orientation = row.get("currentOrientation")
    if orientation in ("rot0","rot90","rot180","rot270"):
        result["orientation"] = orientation
    backlight = row.get("backlightState")
    if backlight in ("on","off","unknown"):
        result["backlight_state"] = backlight
    return result


async def interaction_metadata(rsd, services):
    from pymobiledevice3.remote.core_device.device_info import DeviceInfoService
    from pymobiledevice3.remote.core_device.hid_service import UniversalHIDServiceService
    from pymobiledevice3.services.notification_proxy import RemoteNotificationProxyService
    from packaging.version import Version

    # No frame capture, foreground content, touch, key, or accessibility
    # focus operations. A service advertisement never grants input authority.
    evidence = {key:name in services for key,name in INTERACTION_SERVICES.items()}
    evidence["lock_state"] = "unknown"
    evidence["touch_transport_queried"] = False
    try:
        async with DeviceInfoService(rsd) as device:
            try:
                display = await asyncio.wait_for(device.get_display_info(), timeout=4)
                evidence.update(primary_display_metadata(display))
            except Exception:
                pass
            try:
                lock = await asyncio.wait_for(device.get_lockstate(),timeout=3)
                if isinstance(lock,dict):
                    values = [lock[k] for k in ("locked","isLocked","deviceLocked") if k in lock]
                    if values and all(type(v) is bool and v == values[0] for v in values):
                        evidence["lock_state"] = "locked" if values[0] else "unlocked"
            except Exception:
                pass
    except Exception:
        pass
    # The upstream notification-state API is supported only from iOS 27.2.
    # Do not send unsupported requests or infer an unlocked state from silence.
    if evidence["lock_state"] == "unknown" and Version(rsd.product_version) >= Version("27.2"):
        try:
            async with RemoteNotificationProxyService(rsd) as relay:
                state = await asyncio.wait_for(relay.notify_get_state("com.apple.springboard.lockstate"),timeout=3)
                if type(state) is int and state in (0,1):
                    # The proxy also returns zero for an unset notification.
                    # Do not promote zero alone to a positive unlocked receipt.
                    if state == 1:
                        evidence["lock_state"] = "locked"
        except Exception:
            pass
    if evidence["touch_service_advertised"]:
        try:
            async with UniversalHIDServiceService(rsd) as hid:
                response = await asyncio.wait_for(hid.list_connected_services(),timeout=4)
                rows = response.get("connectedServices") if isinstance(response,dict) else None
                if isinstance(rows,list) and len(rows)<=256 and all(isinstance(row,dict) for row in rows):
                    evidence["touch_transport_queried"] = True
                    evidence["hid_surface_count"] = len(rows)
        except Exception:
            pass
    return evidence


async def collect(udid, interaction=False):
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.mobile_image_mounter import MobileImageMounterService
    from pymobiledevice3.remote.tunnel_service import CoreDeviceTunnelProxy
    from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel, TunnelProvider

    result = {"developer_status": "unavailable", "remote_xpc_connected": False}
    async with await create_using_usbmux(serial=udid, autopair=False,
            connection_type="USB", pair_timeout=0) as client:
        if not client.paired or not client.session_id or not isinstance(client.udid,str) or client.udid.casefold()!=udid.casefold():
            return {**result, "developer_status": "trust_required"}
        enabled = await client.get_value("com.apple.security.mac.amfi", "DeveloperModeStatus")
        if type(enabled) is not bool:
            return result
        result["developer_mode"] = enabled
        if not enabled:
            return {**result, "developer_status": "developer_mode_required"}
        try:
            async with MobileImageMounterService(client) as mounter:
                mounted = await mounter.is_image_mounted("Personalized")
                if type(mounted) is bool:
                    result["developer_image_mounted"] = mounted
        except Exception:
            # Unknown is distinct from an explicitly unmounted image.
            pass

    async def provider():
        # The upstream default provider may select another transport. Bind to
        # the existing USB pairing only and prohibit RemotePairing fallback.
        client = await create_using_usbmux(serial=udid, autopair=False,
                    connection_type="USB", pair_timeout=0)
        try:
            if not client.paired or not client.session_id or not isinstance(client.udid,str) or client.udid.casefold()!=udid.casefold():
                raise RuntimeError("trust_required")
            if await client.get_value("com.apple.security.mac.amfi", "DeveloperModeStatus") is not True:
                raise RuntimeError("developer_mode_required")
            return TunnelProvider(await CoreDeviceTunnelProxy.create(client), client)
        except BaseException:
            await client.close()
            raise

    tunnel = UserspaceRsdTunnel(serial=udid, autopair=False,
              remotepairing_fallback=False, provider_factory=provider)
    try:
        async with tunnel as rsd:
            if not isinstance(rsd.udid, str) or rsd.udid.casefold() != udid.casefold():
                return {**result, "developer_status": "identity_mismatch"}
            services = rsd.peer_info.get("Services")
            if not isinstance(services, dict) or len(services) > 4096:
                return result
            evidence = {"remote_service_count": len(services)}
            for field, prefixes in SERVICE_GROUPS.items():
                evidence[field] = any(isinstance(name, str) and name.startswith(prefixes)
                                      for name in services)
            if interaction:
                evidence.update(await interaction_metadata(rsd,services))
        # A successful result requires the context manager to finish cleanup.
        return {**result, **evidence, "remote_xpc_connected": True,
                "developer_status": "tunnel_verified"}
    except Exception:
        return result


if __name__ == "__main__":
    try:
        from loguru import logger
        logger.remove()
        logging.disable(logging.CRITICAL)
        if (len(sys.argv) not in (2,3) or not re.fullmatch(r"[A-Za-z0-9-]{8,128}", sys.argv[1])
                or (len(sys.argv)==3 and sys.argv[2]!="interaction")):
            raise ValueError
        interaction = len(sys.argv)==3
        print(json.dumps(asyncio.run(asyncio.wait_for(collect(sys.argv[1],interaction), timeout=30 if interaction else 18))))
    except Exception:
        print('{"developer_status":"unavailable","remote_xpc_connected":false}')
