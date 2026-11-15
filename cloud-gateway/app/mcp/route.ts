import { env } from "cloudflare:workers";
import { gateway } from "../../lib/rdc-gateway";

export const dynamic = "force-dynamic";
export async function POST(request: Request) { return gateway.mcp(request, env); }
export async function GET() { return new Response("RDC uses JSON-RPC POST requests.", { status: 405, headers: { Allow: "POST" } }); }
