# RDC capacity and terminal recovery execution plan
TOC Ministries | 2026-11-17

1. Root-cause trace: capture gateway_busy, status and REA D1 retained vs active query behavior.
2. TDD: RED reproducer, bounded read-only reclaim, GREEN focused and full Node suite with original request identity safety.
3. Run independent test lanes in parallel: Node gateway, Python terminal/relay, Python code-context/edits. Retain exact exit statuses and bounded logs without changing live services.
4. Run complete Python suite, gateway suite, diff check, compile/lint where dependencies are ready. No skipped-failure claims.
5. Publish through authorized GitHub permissions only; keep other owner branches, existing main and live Site unchanged if denied.
6. Update existing private ChatGPT plugin skills in place after comparing current release. Preserve App, identity, binding and audience. Do not claim plugin update installs cloud code.
7. After independently qualified gateway release and protected rollback, perform fresh real @RDC acceptance. Keep block open if command refuses. Benchmark against DC once fixed.
