# RDC testing and qualification policy

Effective November 25, 2026. Supersedes the November 19 fixed 100-case ceiling.
The owner removed the universal count limit. Existing 100-case reports and
historic campaign ledgers remain unchanged as evidence, not current constraints.

Use enough relevant tests and live samples to establish the actual acceptance
criteria. Do not stop solely because 100 checks were executed. Each campaign
must declare its purpose, test selections, expected duration, cleanup strategy,
and applicable resource or device limits. Count failed attempts, retries and
all actual executions. Distinct campaigns must have distinct objectives, not
be used to hide failures.

The existing manifest filename and governor remain compatible entry points.
A null max_cases means no universal count ceiling; explicitly configured
campaign or CI limits are supported. Current CI selections remain small,
repeatable baseline selections, not maximum coverage. Larger suites may be
declared and run where warranted. Test discovery, execution counts and source
paths must remain validated. Preserve timeouts and fail-closed behavior for
invalid plans, uncertain device actions and unsafe execution conditions.

For performance acceptance, collect fresh correct samples under comparable
conditions. Report actual median and tail latency, failures and limitations.
Never claim success based on skipped tests or early acknowledgements.
Keep owner authorization, protected data, test device identity, independent
review where available, and verified rollback intact. For physical tests,
continue through the requested acceptance criteria or a concrete blocker;
stop on uncertain input, unavailable capabilities, loss of device identity,
or inability to verify cleanup.

Use scripts/rdc_test_budget.py --campaign NAME --dry-run for selection review,
then execute the planned campaign. No change to production installation,
network permissions, signing restrictions, or release qualification follows
automatically from removing the count ceiling.
