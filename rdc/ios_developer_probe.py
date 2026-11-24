"""Isolated, read-only iOS developer readiness probe over an exact USB device.

No mounting, app installation, new pairing, network pairing, administrator
privileges, exposed listener or screen/content capture. The temporary tunnel
is closed before returning a successful result.
"""
import asyncio
import json
import logging
import re
import sys

SERVICE_GROUPS = {
    "application_service_advertised": ("com.apple.coredevice.appservice",),
    "device_info_service_advertised": ("com.apple.coredevice.deviceinfo",),
    "debug_service_advertised": ("com.apple.debugserver",),
    "instruments_service_advertised": ("com.apple.instruments",),
    "image_service_advertised": ("com.apple.mobile.mobile_image_mounter",),
}


async def collect(udid):
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.mobile_image_mounter import MobileImageMounterService
    from pymobiledevice3.remote.tunnel_service import CoreDeviceTunnelProxy
    from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel, TunnelProvider

    result = {"developer_status": "unavailable", "remote_xpc_connected": False}
    async with await create_using_usbmux(serial=udid, autopair=False,
            connection_type="USB", pair_timeout=0) as client:
        if not client.paired or not client.session_id:
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
            if not client.paired or not client.session_id:
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
        if len(sys.argv) != 2 or not re.fullmatch(r"[A-Za-z0-9-]{8,128}", sys.argv[1]):
            raise ValueError
        print(json.dumps(asyncio.run(asyncio.wait_for(collect(sys.argv[1]), timeout=18))))
    except Exception:
        print('{"developer_status":"unavailable","remote_xpc_connected":false}')
