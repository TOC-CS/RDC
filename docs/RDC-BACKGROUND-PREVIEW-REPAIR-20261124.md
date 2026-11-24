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

## Verification

Five failing behavior assertions were reproduced before implementation: three background policy defects and two legacy presentation defects. The next six selected checks passed. A subsequent 28-case source/browser regression selection passed without skips, including a real headless Playwright session and three bundled-iframe UI tests. The initial preview test selector accidentally selected two existing contract cases; both executions are charged in the cumulative ledger and were not represented as red evidence.

The test governor preflight was used. All executions, including repeats and nested native input checks, are tracked against one cumulative 100-slot maximum. The complete test library was not run. No new latency superiority claim is made.

## Installation and remaining acceptance

A narrow package is prepared against SHA-256 hashes of the installed source. It contains only the new policy and preview hunks; it does not install the larger V2 branch. The package must be revalidated immediately before installation. Preserve the installed configuration, pairing, journals and source backups.

Seven additional checks passed against the narrow patch applied to a copy of the installed worker source. The cumulative ledger charges 62/100 slots, including one live guard recheck failure and conservative nested-case accounting.

The source candidate is not a live worker upgrade. Applying the new Python policy requires an orderly worker restart, which ends its three existing dedicated browser sessions. Active jobs must be checked before restart. The deployed gateway's embedded preview asset also requires a separately verified asset update; local asset changes alone do not update the ChatGPT widget.

Real ChatGPT floating placement is still OPEN. Background YouTube editing requires authentication in an independent browser session; ordinary Chrome authentication does not imply the headless browser is signed in. Never copy cookie databases or silently fall back to the owner's tabs.

Keep the existing V2 migration and merge hold. This patch does not qualify the broader latency or platform release gates.
