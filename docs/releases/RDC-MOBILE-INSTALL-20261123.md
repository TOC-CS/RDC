# RDC mobile installation development evidence, 2026-11-23

Base source: fb631e8 (audit recovery branch). Isolated mobile candidate only.
No live gateway, plugin, device pairing, production service or public release
was changed. Existing six live acceptance gates and release hold remain open.

| Check | Result |
| --- | --- |
| New mobile installation tests (initial red run) | 5 executed; expected 3 failures, 2 errors before implementation |
| New mobile installation tests (green run) | 5/5 passed |
| Existing native Appium/ADB synthetic checks | 33/33 passed |
| Existing mobile worker integration | 5/5 passed |
| Existing standalone gateway checks | 19/19 passed |

Combined development execution: 67 total, including the 5 deliberately failing
pre-implementation checks; 62/62 final selected checks passed. This total is
under the single owner-mandated 100-case ceiling. Unselected cases remain
untested. JavaScript syntax and Git whitespace checks passed.

The iMac has Apple Command Line Tools only, no full Xcode, no Appium
installation, no working JDK, and no Android SDK/ADB executable. The connected
device inventory lists the iMac and VPS only, with no physical phone.
Real iPhone/iPad and Android installation, native automation, live host
performance, public TLS, signed IPA/APK and store distribution remain unverified.

## Follow-up: real iPhone USB onboarding

Five additional targeted USB onboarding tests passed. The owner-connected
physical iPhone reported product type iPhone18,2 and iOS 26.6.1. The Mac's
USB multiplexer enumerated one USB device; the device service answered, and
its existing host trust was accepted. The owner-local profile generator
created a permission-600 fragment for the exact USB device outside the
repository, without modifying live worker configuration or phone data.
These are USB diagnostic and configuration results only. Full Xcode is absent,
and the host has approximately 6.2 GiB free. Native control and signed
distribution remain open.

## Follow-up: live iOS metrics through RDC worker

Installed the Homebrew libimobiledevice 1.4.0_3 package and required small
dependencies on the authorized iMac. Existing trust validated independently.
A further five synthetic exact-target, schema, privacy, and missing-library
tests passed. A separately isolated RDC Engine using the private iOS profile
returned all six allowlisted live metrics via rdc_mobile_ios_status: storage
capacity, available data capacity, total data capacity, charge percentage,
charging state, and Developer Mode. USB trust and iOS version were also
confirmed. No personal data or device identifier was returned or committed.
No live production worker or plugin change, phone data change, or native
automation session was made. Native controls remain open pending device
Developer Mode, Xcode, and signed WebDriverAgent. Host free space was 9.9 GiB.
The five additional source tests plus this focused live check remain within
the cumulative 100-check campaign ceiling.

## Follow-up: alternative iOS communication backends

PyMobileDevice3 11.63.1 installed in the default isolated uv environment.
Go-iOS 1.3.2 installed from the official npm package; its bundled macOS
universal executable was placed in the private RDC tools directory
without running the package postinstall script. Both communicated with
the owner-selected physical iOS 26.6.1 device. Ten selected source checks
(5 new backend checks, 5 existing iOS status checks) passed. An isolated
RDC Engine returned all six metrics with the default PyMobileDevice3
backend and independently verified the Go-iOS device identity.
libimobiledevice fallback is retained. No tunnel daemon, native UI action,
signed application installation, production changes or phone data changes.
Developer Mode remained disabled. No live release gates are closed.

## Follow-up: developer mode, mirroring and native developer image

Owner enabled Developer Mode and disabled the Mac's Internet Sharing.
The connected Apple iPhone Mirroring window was verified without capturing
phone content. Five new mirroring software checks and three developer
preflight checks passed. An isolated RDC worker successfully detected
available mirroring navigation commands and opened and closed a no-root
USB RemoteXPC tunnel. The initially advertised service count was 61.

The initial PersonalizedDMG mount failed; readback showed no mounted image.
The phone subsequently confirmed compatible Cryptex service and no existing
developer image. A single owner-authorized Apple-personalized Cryptex
first installation succeeded without replacing or uninstalling an image.
Independent readback confirmed both the installed record and mount. The
subsequent developer preflight returned 82 advertised services, including
application and device-info services. Device trust and Developer Mode were
still enabled. No personal device content was accessed or changed by these
development operations. Physical UI action qualification, signed companion
packaging, wireless direct control, and existing production release gates
remain open. No production deployment or merge occurred.
