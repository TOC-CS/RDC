import { env } from "cloudflare:workers";
import { rdc2Edge } from "../../../lib/v2/rdc2-edge";

export const dynamic = "force-dynamic";
export async function POST(request: Request) {
  return rdc2Edge.mcp(request, env);
}
export async function GET() {
  return new Response("RDC 2.0 requires authenticated JSON-RPC POST.", {
    status: 405, headers: { Allow: "POST", "Cache-Control": "no-store" },
  });
}
