"""Fixed, isolated PyMobileDevice3 read-only helper; no automatic pairing."""
import asyncio
import json
import re
import sys

FIELDS = (
    ("com.apple.disk_usage","TotalDiskCapacity","storage_total_bytes"),
    ("com.apple.disk_usage","TotalDataAvailable","storage_available_bytes"),
    ("com.apple.disk_usage","TotalDataCapacity","storage_data_capacity_bytes"),
    ("com.apple.mobile.battery","BatteryCurrentCapacity","battery_percent"),
    ("com.apple.mobile.battery","BatteryIsCharging","charging"),
    ("com.apple.security.mac.amfi","DeveloperModeStatus","developer_mode"),
)

async def collect(udid):
    from pymobiledevice3.lockdown import create_using_usbmux
    async with await create_using_usbmux(serial=udid,autopair=False,
            connection_type="USB",pair_timeout=0) as client:
        if not getattr(client,"paired",False) or not getattr(client,"session_id",None):
            return {}
        values={}
        for domain,key,name in FIELDS:
            try:
                value=await asyncio.wait_for(client.get_value(domain,key),timeout=2)
            except Exception:
                continue
            if type(value) in (int,bool):
                values[name]=value
        return values

if __name__=="__main__":
    try:
        if len(sys.argv)!=2 or not re.fullmatch(r"[A-Za-z0-9-]{8,128}",sys.argv[1]):
            raise ValueError
        print(json.dumps(asyncio.run(asyncio.wait_for(collect(sys.argv[1]),timeout=9))))
    except Exception:
        print("{}")
