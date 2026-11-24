# RDC background workflow and preview repair

TOC Ministries. Source repair for the November 23 owner report.

## Observed failure and immediate containment

The installed worker reports 0.1.0a8 and shared native desktop mode. Its Playwright browser has independent headless contexts, but the active YouTube audit used a Python helper that sends AppleScript to regular Chrome tabs. Its long-running collector repeatedly navigated a shared tab.

The exact collector job was cancelled and read back as cancelled. Both shared-Chrome helper entry points were initially guarded before issuing AppleScript. The original helper was preserved beside the file with the suffix .before-background-stop. Existing collected evidence remains intact.

A later verification found that another active SEO workflow had removed the guard, moved its tabs to a different Chrome window and restarted collection and metadata-edit jobs. The helper now claims owner reauthorization. This claim is recorded as concurrent workflow state, not treated as a new instruction in this repair session. A user clarification is pending before stopping those jobs again. The live guard check failed before dispatching any Chrome command because the test patched subprocess.run. Persistent desktop containment is therefore OPEN.

## Source repairs

- New background_only configuration defaults to true. Native pointer, typing, keyboard and preview resize operations fail before approval or dispatch. Background WebDriver creation fails before opening a session. Independent Playwright, file reads and terminal jobs remain available.
- An owner can explicitly configure background_only=false for intentional foreground work. Existing native-input approval checks still apply.
- Background-only is an adapter policy, not an operating-system sandbox for arbitrary terminal programs. Shell jobs can still call desktop APIs. Tool descriptions explicitly prohibit using them to bypass background work. The exact offending helper is separately stopped.
- Preview Float is available on a user click when the documented OpenAI display-mode bridge exists, even if the separate MCP mode list omits PiP. Automatic requests still require advertised support. Returned modes are verified; fullscreen substitution returns inline. Source binding, no-replay handling and job-bound teardown remain intact.
- Official reference: https://developers.openai.com/plugins/reference
- OpenAI MCP display documentation and the OpenAI runtime bridge describe different mode capabilities. Presence of a method permits a request; it does not prove live floating support.

The bundle now advertises preview-v10 with all v1-v9 aliases retained, so a new open can select the new resource identity. Gateway assets carry the same tested HTML and job guidance.

## Verification

Five failing behavior assertions were reproduced before implementation: three background policy defects and two legacy presentation defects. The next six selected checks passed. A subsequent 28-case source/browser regression selection passed without skips, including a real headless Playwright session and three bundled-iframe UI tests. The initial preview test selector accidentally selected two existing contract cases; both executions are charged in the cumulative ledger and were not represented as red evidence.

The test governor preflight was used. All executions, including repeats and nested native input checks, are tracked against one cumulative 100-slot maximum. The complete test library was not run. No new latency superiority claim is made.

## Installation and remaining acceptance

A narrow package is prepared against SHA-256 hashes of the installed source. It contains only the new policy and preview hunks; it does not install the larger V2 branch. The package must be revalidated immediately before installation. Preserve the installed configuration, pairing, journals and source backups.

Two final resource tests passed after a deliberate version-red check, including all historical resource aliases. Seven additional checks passed against the narrow patch applied to a copy of the installed worker source. The cumulative ledger charges 76/100 slots, including one live guard recheck failure and conservative nested-case accounting.

The source candidate is not a live worker upgrade. Applying the new Python policy requires an orderly worker restart, which ends its three existing dedicated browser sessions. Active jobs must be checked before restart. The deployed gateway's embedded preview asset also requires a separately verified asset update; local asset changes alone do not update the ChatGPT widget.

Real ChatGPT floating placement is still OPEN. Background YouTube editing requires authentication in an independent browser session; ordinary Chrome authentication does not imply the headless browser is signed in. Never copy cookie databases or silently fall back to the owner's tabs.

Keep the existing V2 migration and merge hold. This patch does not qualify the broader latency or platform release gates.

## Continuation, November 24

A background preview could still request `resize_to_view=true`, creating a pending owner approval for a grant the background policy would later refuse to use. A test-first repair now rejects this grant before approval or dispatch while preserving observational windows and explicit foreground owner approval. One expected red failure among three cases was reproduced; all three passed after the change, and all three passed again against the isolated narrow installed-source copy. The cumulative campaign is 85/100 charged slots (15 remain). All six installed preimages and candidate hashes were revalidated, and the narrow package manifest now includes the additional guard. No production files, active browser sessions or gateway deployments were changed. Live verification and activation remain open.

### Legacy live-transport compatibility

The prepared preview-v10 gateway catalog and installed a8 worker originally omitted the optional `job_id` accepted by the newer source. The isolated installed-source test reproduced rejection of the job-bound preview request, then passed after backporting the exact-job schema, terminal-state lookup and no-extra-capture completion behavior. The narrow gateway candidate now advertises the same optional UUID for open/frame. The original authenticated transport, approval behavior, resource identity aliases and session isolation remain unchanged. The cumulative conservative charge is 94/100; the remaining six slots are reserved for activation/readback. The stage manifests identify the exact six worker files and two gateway files, independently of the unreleased V2 transport. Installation and actual host floating still require live readback.

## Publication and installation readback

- The draft repair PR #23 has been published on the existing repair branch; the protected V2 PR #21 remains separate and unmerged.
- The existing private ChatGPT plugin is published at v1.0.36, with both version manifests and the original App binding verified. Its 27-file published archive matches the local versioned plugin cache, and v1.0.35 remains available. Client UI refresh is not yet verified.
- All six narrow worker source/bundle files were atomically installed and hash-verified on disk against their exact prepared manifest, with six matching preimage rollback copies. The existing worker and relay configurations were unchanged. The running a8 daemon has not been restarted because the live browser list still reports three open sessions, including a Remotion Studio source. The preview bundle is v10 on disk; live background-policy activation, gateway v10 activation and actual host floating placement remain OPEN. No V2 transport, pairing, permission, database migration or release gate was changed.
- The previously measured standalone VPS and loopback speeds remain development evidence. The existing ChatGPT link continues on the older gateway; do not represent source or cache synchronization as live speed qualification.
