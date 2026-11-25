#!/usr/bin/env python3
"""Native iOS packaging with a separately obtained, owner-authorized SDK.

Never downloads SDKs, opens Xcode, invokes xcodebuild, creates or exports
credentials, alters device settings, signs ad hoc, or installs applications.
The optional signing command requires a matching Apple development certificate
already held in the owner's keychain and a device-specific provisioning profile.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
BUNDLE_ID = "org.tocministries.rdc.mobile"
EXECUTABLE = "RDCMobile"
MIN_IOS = "17.0"
DEFAULT_COMPILER = "/Library/Developer/CommandLineTools/usr/bin/swiftc"


def reject_xcode_path(path: Path) -> Path:
    path = path.expanduser().resolve()
    if any(part.casefold().startswith("xcode") and part.casefold().endswith(".app")
           for part in path.parts):
        raise ValueError("Xcode application paths are excluded by owner policy.")
    return path


def validate_sdk(path: Path) -> Path:
    sdk = reject_xcode_path(path)
    if not sdk.is_dir():
        raise ValueError("A separately obtained, licensed iPhoneOS SDK is required.")
    metadata = sdk / "SDKSettings.json"
    if metadata.is_file():
        obj = json.loads(metadata.read_text())
    else:
        metadata = sdk / "SDKSettings.plist"
        if not metadata.is_file():
            raise ValueError("The supplied SDK has no SDK settings.")
        obj = plistlib.loads(metadata.read_bytes())
    name = obj.get("CanonicalName","") if isinstance(obj,dict) else ""
    if not isinstance(name,str) or not re.fullmatch(r"iphoneos(?:[0-9]+(?:\.[0-9]+)*)?",name.lower()):
        raise ValueError("Use an actual iPhoneOS device SDK, not a macOS or simulator SDK.")
    for framework in ("Foundation","SwiftUI"):
        if not (sdk/"System/Library/Frameworks"/(framework+".framework")).is_dir():
            raise ValueError("The SDK is missing a required public framework.")
    return sdk


def validate_compiler(path: Path) -> Path:
    compiler = reject_xcode_path(path)
    # swiftc may be a symlink to swift-driver in an approved toolchain.
    if not compiler.is_file() or not os.access(compiler,os.X_OK):
        raise ValueError("Provide an installed standalone Swift compiler.")
    if path.name != "swiftc":
        raise ValueError("Select the Swift compiler executable named swiftc.")
    return path.expanduser().absolute()


def bundle_info():
    phone_icons = {"CFBundlePrimaryIcon":{"CFBundleIconFiles":["AppIcon60"],
                                         "UIPrerenderedIcon":False}}
    pad_icons = {"CFBundlePrimaryIcon":{"CFBundleIconFiles":["AppIcon60","AppIcon76","AppIcon83.5"],
                                       "UIPrerenderedIcon":False}}
    return {
        "CFBundleIdentifier":BUNDLE_ID,
        "CFBundleExecutable":EXECUTABLE,
        "CFBundleName":"RDC Mobile",
        "CFBundleDisplayName":"RDC Mobile",
        "CFBundlePackageType":"APPL",
        "CFBundleInfoDictionaryVersion":"6.0",
        "CFBundleShortVersionString":"0.1.1",
        "CFBundleVersion":"2",
        "CFBundleSupportedPlatforms":["iPhoneOS"],
        "MinimumOSVersion":MIN_IOS,
        "LSRequiresIPhoneOS":True,
        "UIDeviceFamily":[1,2],
        "UILaunchScreen":{},
        "NSLocalNetworkUsageDescription":"Connect to your owner-authorized RDC gateway on your local network.",
        "CFBundleIcons":phone_icons,
        "CFBundleIcons~ipad":pad_icons,
    }


def compile_command(compiler: Path,sdk: Path,output: Path):
    return [str(compiler),"-sdk",str(sdk),"-target","arm64-apple-ios"+MIN_IOS,
            "-swift-version","5","-parse-as-library","-O",
            str(HERE/"RDCMobile/GatewayContract.swift"),
            str(HERE/"RDCMobile/RDCMobileApp.swift"),
            str(HERE/"RDCMobile/LocalTerminal.swift"),
            str(HERE/"RDCMobile/LocalTerminalView.swift"),
            "-framework","Foundation","-framework","SwiftUI","-o",str(output)]


def fresh_output(path: Path, suffix: str):
    path = path.expanduser().absolute()
    if path.suffix != suffix or path.exists() or path.is_symlink():
        raise ValueError("Choose a new output path with suffix "+suffix+". Existing files are preserved.")
    path.parent.mkdir(parents=True,exist_ok=True)
    return path


def build(sdk_path: Path,compiler_path: Path,output: Path):
    if sys.platform!="darwin":
        raise ValueError("This standalone compiler adapter currently targets macOS.")
    sdk=validate_sdk(sdk_path)
    compiler=validate_compiler(compiler_path)
    output=fresh_output(output,".app")
    with tempfile.TemporaryDirectory(prefix=".rdc-ios-build-",dir=output.parent) as tmp:
        stage=Path(tmp)/"RDCMobile.app"
        stage.mkdir(mode=0o700)
        (stage/"Info.plist").write_bytes(plistlib.dumps(bundle_info()))
        icon=HERE/"RDCMobile/Assets.xcassets/AppIcon.appiconset/icon.png"
        for filename,size in (("AppIcon60@2x.png",120),("AppIcon60@3x.png",180),
                              ("AppIcon76@2x.png",152),("AppIcon83.5@2x.png",167)):
            subprocess.run(["/usr/bin/sips","-z",str(size),str(size),str(icon),"--out",str(stage/filename)],
                           stdout=subprocess.DEVNULL,check=True,timeout=20)
        # Direct compiler invocation only. Do not allow Xcode project/build
        # tools or an implicit SDK fallback to select the platform.
        env=dict(os.environ)
        env.pop("DEVELOPER_DIR",None)
        env["SDKROOT"]=str(sdk)
        subprocess.run(compile_command(compiler,sdk,stage/EXECUTABLE),
                       env=env,check=True,timeout=300)
        if not (stage/EXECUTABLE).is_file():
            raise ValueError("The compiler did not produce an executable.")
        if output.exists() or output.is_symlink():
            raise ValueError("Output path appeared during compilation.")
        # copytree never overwrites an existing destination.
        shutil.copytree(stage,output)
    return output


def validate_profile(profile,device,certificate_sha1,now=None):
    """Validate exact target, bundle entitlement and allowed certificate.

    This is a local admission check, not a claim of cryptographic profile
    validity. Apple's installation service remains the signing authority.
    """
    if (not isinstance(device,str) or not re.fullmatch(r"[A-Za-z0-9-]{8,128}",device)
            or not isinstance(certificate_sha1,str) or not re.fullmatch(r"[0-9A-Fa-f]{40}",certificate_sha1)
            or not isinstance(profile,dict)):
        raise ValueError("Invalid development signing parameters.")
    now=now or datetime.now(timezone.utc)
    expiry=profile.get("ExpirationDate")
    if not isinstance(expiry,datetime):
        raise ValueError("Provisioning profile expiration is missing.")
    if expiry.tzinfo is None:
        expiry=expiry.replace(tzinfo=timezone.utc)
    if expiry<=now:
        raise ValueError("The provisioning profile has expired.")
    devices=profile.get("ProvisionedDevices")
    if (not isinstance(devices,list)
            or not any(isinstance(d,str) and d.casefold()==device.casefold() for d in devices)):
        raise ValueError("The exact owner-selected device is not provisioned.")
    platforms=profile.get("Platform")
    if not isinstance(platforms,list) or "iOS" not in platforms:
        raise ValueError("The profile is not an iOS profile.")
    teams=profile.get("TeamIdentifier")
    ent=profile.get("Entitlements")
    if not isinstance(teams,list) or len(teams)!=1 or not isinstance(teams[0],str):
        raise ValueError("The profile must identify one signing team.")
    team=teams[0]
    prefixes=profile.get("ApplicationIdentifierPrefix")
    if (not re.fullmatch(r"[A-Z0-9]{10}",team)
            or not isinstance(prefixes,list) or len(prefixes)!=1
            or not isinstance(prefixes[0],str) or not re.fullmatch(r"[A-Z0-9]{10}",prefixes[0])
            or not isinstance(ent,dict)
            or ent.get("application-identifier")!=prefixes[0]+"."+BUNDLE_ID
            or ent.get("com.apple.developer.team-identifier")!=team
            or ent.get("get-task-allow") is not True):
        raise ValueError("An explicit development profile for the RDC bundle is required.")
    certs=profile.get("DeveloperCertificates")
    if (not isinstance(certs,list)
            or not any(isinstance(c,bytes) and hashlib.sha1(c).hexdigest().upper()==certificate_sha1.upper()
                       for c in certs)):
        raise ValueError("The selected signing certificate is not authorized by this profile.")
    # Use only the minimal entitlements this test app needs; never copy broad
    # permissions or capabilities from the provisioning profile.
    return {"application-identifier":ent["application-identifier"],
            "com.apple.developer.team-identifier":team,"get-task-allow":True}


def sign(verified_app: Path,profile_path: Path,device: str,identity: str,output: Path):
    if sys.platform!="darwin":
        raise ValueError("This signing adapter requires the macOS keychain and codesign.")
    app=reject_xcode_path(verified_app)
    if app.suffix!=".app" or not app.is_dir():
        raise ValueError("Select the compiled unsigned RDC application.")
    info=plistlib.loads((app/"Info.plist").read_bytes())
    if info.get("CFBundleIdentifier")!=BUNDLE_ID or info.get("CFBundleExecutable")!=EXECUTABLE:
        raise ValueError("This is not the RDC companion bundle.")
    if not (app/EXECUTABLE).is_file() or (app/EXECUTABLE).is_symlink():
        raise ValueError("The RDC executable is missing or unsafe.")
    if any(p.is_symlink() for p in app.rglob("*")):
        raise ValueError("Refuse symbolic links in a signing candidate.")
    if (app/"_CodeSignature").exists() or (app/"embedded.mobileprovision").exists():
        raise ValueError("Sign an unsigned candidate only; existing signed bundles are preserved.")
    if not re.fullmatch(r"[0-9A-Fa-f]{40}",identity):
        raise ValueError("Specify the exact Apple signing identity SHA-1.")
    profile_path=profile_path.expanduser().resolve()
    if not profile_path.is_file() or profile_path.stat().st_size>8*1024*1024:
        raise ValueError("Select an owner-held Apple provisioning profile.")
    output=fresh_output(output,".ipa")
    payload=subprocess.run(["/usr/bin/security","cms","-D","-i",str(profile_path)],
                  capture_output=True,check=True,timeout=15).stdout
    if len(payload)>8*1024*1024:
        raise ValueError("Provisioning profile output is too large.")
    ent=validate_profile(plistlib.loads(payload),device,identity)
    identities=subprocess.run(["/usr/bin/security","find-identity","-v","-p","codesigning"],
                        capture_output=True,text=True,check=True,timeout=15).stdout
    if not re.search(r"(?im)^\s*\d+\)\s+"+re.escape(identity)+r"\s",identities):
        raise ValueError("The selected Apple signing identity is not available in the keychain.")
    with tempfile.TemporaryDirectory(prefix=".rdc-ios-sign-",dir=output.parent) as temp:
        base=Path(temp)
        stage=base/"Payload/RDCMobile.app"
        shutil.copytree(app,stage)
        shutil.copyfile(profile_path,stage/"embedded.mobileprovision")
        ent_path=base/"entitlements.plist"
        ent_path.write_bytes(plistlib.dumps(ent))
        subprocess.run(["/usr/bin/codesign","--sign",identity,"--entitlements",str(ent_path),
                        "--timestamp=none",str(stage)],check=True,timeout=90)
        subprocess.run(["/usr/bin/codesign","--verify","--strict",str(stage)],check=True,timeout=30)
        signed=subprocess.run(["/usr/bin/codesign","-d","--entitlements",":-",str(stage)],
                            capture_output=True,check=True,timeout=20).stdout
        if plistlib.loads(signed)!=ent:
            raise ValueError("Signed entitlements do not match the minimal approved grant.")
        # Exclusive creation: never overwrite a prior package. Preserve only
        # the resulting package; never export the certificate's private key.
        with output.open("xb") as file:
            try:
                with zipfile.ZipFile(file,"w",compression=zipfile.ZIP_DEFLATED) as archive:
                    for item in sorted(stage.rglob("*")):
                        if item.is_file():
                            archive.write(item,item.relative_to(base))
            except BaseException:
                file.close()
                output.unlink(missing_ok=True)
                raise
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_subparsers(dest="action",required=True)
    doctor=actions.add_parser("doctor")
    doctor.add_argument("--sdk",type=Path)
    doctor.add_argument("--swiftc",type=Path,default=Path(DEFAULT_COMPILER))
    compile=actions.add_parser("build")
    compile.add_argument("--sdk",type=Path,required=True)
    compile.add_argument("--swiftc",type=Path,default=Path(DEFAULT_COMPILER))
    compile.add_argument("--out",type=Path,required=True)
    signing=actions.add_parser("sign")
    signing.add_argument("--app",type=Path,required=True)
    signing.add_argument("--profile",type=Path,required=True)
    signing.add_argument("--device",required=True,help="Exact locally authorized device identifier; never printed.")
    signing.add_argument("--identity",required=True,help="Exact local certificate SHA-1; never printed.")
    signing.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.action=="doctor":
            validate_compiler(args.swiftc)
            if args.sdk is None:
                print(json.dumps({"standalone_compiler":True,"ios_sdk_available":False,
                                  "native_compile_ready":False,"xcode_used":False}))
                return
            validate_sdk(args.sdk)
            print(json.dumps({"standalone_compiler":True,"ios_sdk_available":True,
                              "native_compile_ready":sys.platform=="darwin","xcode_used":False}))
        elif args.action=="build":
            build(args.sdk,args.swiftc,args.out)
            print("Unsigned RDC app compiled. Apple provisioning and signing are still required.")
        else:
            sign(args.app,args.profile,args.device,args.identity,args.out)
            print("Development IPA signed and locally verified. No installation attempted.")
    except (ValueError,OSError,subprocess.SubprocessError,plistlib.InvalidFileException):
        # Avoid emitting sensitive provisioning/profile data or identity values.
        parser.exit(1,"Native packaging prerequisite or verification failed. Inspect the local owner-selected inputs.\n")


if __name__=="__main__":
    main()
