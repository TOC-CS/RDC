# Local mobile driver connection reuse

Development qualification only. The deployed worker is unchanged.

The native mobile adapter previously built a new urllib opener and closed its
TCP connection for every request. Configured HTTP loopback drivers now reuse
one connection per exact endpoint. HTTPS retains its existing verified
transport. Redirects, malformed or truncated messages and oversized responses
are rejected. A failed mutation is never resent. Retained sockets close on
failure and adapter shutdown.

## Evidence

The affected source regression selection passed 107 tests. It includes actual
HTTP server cases for connection reuse, lost mutation responses, redirects,
invalid sessions, response limits, endpoint isolation, socket cleanup,
truncation, ambiguous framing and malformed JSON.

A paired host-only fixture benchmark used 30 samples per variant, each with
the same 18 verified requests. Trial order alternated. Response headers and
body were coalesced and accepted sockets used TCP_NODELAY.

| Measurement | Previous transport | Reused connection |
| --- | ---: | ---: |
| Median, 18 requests | 184.435 ms | 3.422 ms |
| 95th percentile | 330.074 ms | 6.935 ms |
| TCP connections, 540 requests | 540 | 1 |

The median saving was 181.013 ms. These numbers measure synthetic local HTTP
transport. They exclude native event synthesis, screenshots, cloud transport
and model response time. Physical mobile responsiveness remains unqualified.

Socket timeouts still bound inactivity rather than total elapsed response
time. The change does not establish an absolute request deadline.
