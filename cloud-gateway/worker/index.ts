import handler from "vinext/server/fetch-handler";
import { runWithConnectorBinding } from "../lib/connector-context";
import { rdc2Edge } from "../lib/v2/rdc2-edge";
import type { ConnectorBinding } from "../lib/connector-contract.mjs";

const worker = {
  fetch(request: Request, env: Cloudflare.Env, ctx: ExecutionContext<{ CONNECTORS?: ConnectorBinding }>) {
    // Native WebSocket upgrade, only through the separately gated V2 transport.
    if (new URL(request.url).pathname === "/v2/device/socket") {
      return rdc2Edge.deviceSocket(request, env);
    }
    if (new URL(request.url).pathname === "/v2/device/result") {
      return rdc2Edge.deviceResult(request, env);
    }
    let binding = ctx.props?.CONNECTORS;
    // Local preview emulates the same request-scoped capability. This branch and
    // the auxiliary service binding are absent from production builds.
    if (import.meta.env.DEV && !binding && env.CONNECTORS) {
      const preview = env.CONNECTORS;
      const expiresAt = Date.now() + 60_000;
      binding = {
        async getContext() {
          if (Date.now() >= expiresAt) return { status: "request_context_expired" };
          return preview.getContext?.() ?? { status: "binding_unavailable" };
        },
        async invoke(connectorId, actionName, args) {
          if (Date.now() >= expiresAt) {
            return { status: "request_context_expired", message: "This request has expired. Please try again." };
          }
          return preview.invoke(connectorId, actionName, args);
        },
      };
    }
    return runWithConnectorBinding(binding, () => handler.fetch(request, env, ctx));
  },
};

// Exported for an optional owner-provisioned private Durable Object binding.
// It is not publicly routed or enabled merely by this source export.
export { RDCWakeSignal } from "../lib/rdc-wake.mjs";
// Source-only V2 actor. Requires opt-in private namespace and gateway authorization.
export { RDC2DeviceActor } from "../lib/v2/rdc2-actor.mjs";

export default worker;
