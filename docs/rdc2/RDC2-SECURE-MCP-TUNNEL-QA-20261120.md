# RDC 2.0 Secure MCP Tunnel staging verification

Date: November 20, 2026, Central. This is owner-private isolated QA. It does not activate a ChatGPT connector, public service or production worker.

## Verified release and source

The Linux x86-64 VPS staging host received the official OpenAI tunnel-client v0.0.21 binary. Source: openai/tunnel-client GitHub release v0.0.21. The zip asset tunnel-client-v0.0.21-linux-amd64.zip matched the published SHA-256:
9e91a539e3ae1c436d499f216a1d7514b3c86cc7779032f41b2a05821d74b03a

A safe ZIP extraction verified one tunnel-client Linux ELF executable. The extracted CLI is a 26,222,752-byte executable and returned version 0.0.21+714f2d67844b660af25754f1d19b0360b346b13b. Its help quickstart command ran successfully.

Verified isolated location on the owner VPS:
  /srv/toc/rdc-v2-gateway/qa/tunnel-client-v0.0.21/tunnel-client

The original installer ZIP and temporary extraction on the iMac were deleted only after checksum, CLI and VPS readback succeeded. Nothing was added to the live RDC worker installation.

## Staging safety and evidence

The source-controlled dry-run validator is scripts/rdc2_tunnel_preflight.py. It checks a private config file, recognized tunnel ID shape, loopback HTTP MCP route, private permissions and distinct runtime and gateway token files, and actual executable presence without reading credential contents or starting a daemon.

The test-first campaign initially failed as expected. The corrected source passes eight explicit guarded tests, including a final-config-symlink regression. Separate 100-case core and 16-case release acceptance policy campaigns also passed.

The preflight was then run directly ON the owner VPS, using the verified CLI executable and a placeholder config. The exit code was the expected refusal 2. It verified the executable and local MCP URL shape, while reporting exactly these blockers:
  tunnel_identity
  runtime_key_private
  gateway_client_key_private

The blocker report omitted credential bytes and private file paths. No Platform tunnel, runtime key, ChatGPT plugin or attached client was created or inferred. The VPS original gateway services on 18782, 18784 and 18786 all returned HTTP 200 after the stage.

## Completion boundary

The next protected stage requires the actual authorized Platform tunnel identity, a restricted runtime API key, independent standalone gateway client auth, verified ChatGPT workspace association/permissions and successful real ChatGPT discovery. Only then can source/deployed-revision readback, owner pairing, rollback and mandatory 30+ connected speed samples be tested.

The official tunnel transport has a 120-second request deadline and 10 MiB serialized payload bound, both smaller than some existing RDC V2 worker capabilities. Adapt response handling and verify those limits before accepting a rollout. Never claim the localhost or SSH benchmarks establish ChatGPT-connected speed.

Existing ChatGPT private plugin 1.0.29 and worker 0.1.0a8 remain in place. No v17 migration, production relay replacement, GitHub publication or public DNS/HTTPS change occurred. All six original live speed targets remain OPEN.
