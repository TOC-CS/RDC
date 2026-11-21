"""Bounded live gateway transport diagnostic. NO tool claims, no secrets/output bodies.

Call only with explicit owner authorization. Loads a private on-device relay
configuration without displaying credential bytes, then makes claim=False
authenticated heartbeat requests through the deployed Site. This measures
device-to-gateway transport + D1 housekeeping only, not ChatGPT latency.
"""
from __future__ import annotations
import argparse
import asyncio
from pathlib import Path
import statistics
import time

import httpx2
from rdc.relay import RelayConfig, Gateway


def percentile_nearest(sorted_values, percentile):
    return sorted_values[max(0, (len(sorted_values) * percentile + 99) // 100 - 1)]


async def benchmark(path, samples):
    if type(samples) is not int or samples<1 or samples+2>100:
        raise ValueError('RDC testing hard cap: 100 total live heartbeat samples')
    config = RelayConfig.load(path)
    results = []
    errors = 0
    async with httpx2.AsyncClient(
        trust_env=False, follow_redirects=False, verify=True,
        timeout=httpx2.Timeout(15, connect=5, pool=5),
    ) as client:
        gateway = Gateway(config, client)
        for index in range(samples + 2):
            start = time.perf_counter_ns()
            try:
                operation, _ = await gateway.poll(claim=False)
                if operation is not None:
                    raise RuntimeError('Unexpected operation from heartbeat-only poll')
                duration_ms = (time.perf_counter_ns() - start) / 1_000_000
                if index >= 2:  # two unlabeled connection warmups, never count them
                    results.append(duration_ms)
            except Exception:
                if index >= 2:
                    errors += 1
    times = sorted(results)
    print('route=private_gateway_authenticated_heartbeat_only')
    print('measure=imac_to_cloudflare_device_poll_claim_false')
    print('commands_claimed=0')
    print('attempted=', samples, 'successful=', len(times), 'failed=', errors)
    if times:
        print('p50_ms=', round(statistics.median(times), 3))
        print('p95_ms=', round(percentile_nearest(times, 95), 3))
        print('p99_ms=', round(percentile_nearest(times, 99), 3))
        print('min_ms=', round(times[0], 3), 'max_ms=', round(times[-1], 3))
    print('note=not_a_chatgpt_end_to_end_or_new_site_release_measurement')
    return 0 if errors == 0 and len(times) == samples else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=str(Path.home() /
                        'Library/Application Support/RDC/relay-config.json'))
    parser.add_argument('--samples', type=int, default=30)
    opts = parser.parse_args()
    if not 1 <= opts.samples <= 50:
        parser.error('1 to 50 samples required')
    raise SystemExit(asyncio.run(benchmark(opts.config, opts.samples)))


if __name__ == '__main__':
    main()
