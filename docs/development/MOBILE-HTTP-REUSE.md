# Local mobile driver connection reuse

Development qualification only. The deployed worker is unchanged.

The native mobile adapter previously built a new urllib opener and closed its
TCP connection for every request. Configured HTTP loopback drivers now reuse
one connection per exact endpoint. HTTPS retains its existing verified
transport. Redirects, malformed or truncated messages and oversized responses
are rejected. A failed mutation is never resent. Retained sockets close on
failure, explicit native-session teardown and adapter shutdown.

## Evidence

The affected source regression selection passed 108 tests. It includes actual
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

## Session lifecycle regression

A physical restoration check exposed an idle socket surviving explicit session
teardown and a local driver restart. The adapter now closes the cached endpoint
connection in the teardown finally block. Failed deletion retains its existing
cleanup fence; uncertain creation retains its original identity. No action or
creation is automatically retried.

An actual HTTP server regression reproduces the stale stream failure before the
fix and verifies one creation POST over a new connection afterward. The affected
108-test selection passed. Independent source review found no blocking issue.
The original native runtime was then verified in a separate owned session, with
zero touch input, exact session closure and all temporary service ports closed.

## Combined public preview

The combined preview passed 142 affected tests, including terminal routing,
warm-terminal recovery and the scope-based test planner. Independent source
review found no blocking issue. See the adjacent qualification JSON for the
exact tested revision, selection and log digest. Hosted CI was skipped and
was not counted as passing. This preview contains no experimental native
driver, device-specific evidence, installed worker update or gateway switch.
