// Re-export the actor class so the runtime resolves the [[actors]] type here.
// The exported class name must equal the type in telnyx.toml.
export { CallerSession } from "./caller-session";

const ALLOWED_METHODS = new Set([
  "recordCall",
  "recordVerificationAttempt",
  "isVerified",
  "addRefill",
  "getRefills",
  "setLastIntent",
  "alarm",
]);

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) {
    // Still do a dummy comparison to avoid leaking length via timing,
    // but in practice we can early-return safely here because
    // Buffer.compare is not available in all edge runtimes.
    // A simple fixed-length compare is enough for this use case.
    return false;
  }
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}

function logLine(fields: Record<string, unknown>) {
  console.log(JSON.stringify(fields));
}

async function handleRpc(req: Request, env: Env): Promise<Response> {
  const start = Date.now();
  const traceId = req.headers.get("X-Trace-Id") || "unknown";

  try {
    const token = req.headers.get("X-Internal-Token") || "";
    const expected = ((env as unknown as Record<string, string | undefined>).INTERNAL_TOKEN) || "";
    if (!timingSafeEqual(token, expected)) {
      logLine({
        fn: "caller-session",
        event: "rpc",
        trace_id: traceId,
        outcome: "unauthorized",
        latency_ms: Date.now() - start,
      });
      return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
    }

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      logLine({
        fn: "caller-session",
        event: "rpc",
        trace_id: traceId,
        outcome: "bad_json",
        latency_ms: Date.now() - start,
      });
      return Response.json({ ok: false, error: "invalid json" }, { status: 400 });
    }

    const payload = body as Record<string, unknown>;
    const method = String(payload.method || "");
    const callerKey = String(payload.caller_key || "");
    const args = (payload.args as Record<string, unknown>) ?? {};

    if (!ALLOWED_METHODS.has(method)) {
      logLine({
        fn: "caller-session",
        event: "rpc",
        trace_id: traceId,
        method,
        outcome: "bad_method",
        latency_ms: Date.now() - start,
      });
      return Response.json({ ok: false, error: "bad method" }, { status: 400 });
    }

    if (!callerKey) {
      logLine({
        fn: "caller-session",
        event: "rpc",
        trace_id: traceId,
        method,
        outcome: "missing_caller_key",
        latency_ms: Date.now() - start,
      });
      return Response.json({ ok: false, error: "missing caller_key" }, { status: 400 });
    }

    const stub = env.CALLER_SESSION.idFromName(callerKey);
    // TypeScript doesn't know the dynamic signature; cast through unknown.
    const actorMethod = (stub as unknown as Record<string, (a: Record<string, unknown>) => Promise<unknown>>)[method];
    const result = await actorMethod(args);

    logLine({
      fn: "caller-session",
      event: "rpc",
      trace_id: traceId,
      method,
      caller_key: callerKey,
      outcome: "ok",
      latency_ms: Date.now() - start,
    });

    return Response.json({ ok: true, result });
  } catch (err) {
    logLine({
      fn: "caller-session",
      event: "rpc",
      trace_id: traceId,
      outcome: "error",
      error: String(err),
      latency_ms: Date.now() - start,
    });
    return Response.json({ ok: false, error: String(err) }, { status: 500 });
  }
}

async function handleHealth(env: Env): Promise<Response> {
  const start = Date.now();
  const traceId = `health_${Date.now()}`;
  try {
    const stub = env.CALLER_SESSION.idFromName("health");
    await stub.isVerified({ traceId });
    logLine({
      fn: "caller-session",
      event: "health",
      trace_id: traceId,
      outcome: "ok",
      latency_ms: Date.now() - start,
    });
    return Response.json({ ok: true });
  } catch (err) {
    logLine({
      fn: "caller-session",
      event: "health",
      trace_id: traceId,
      outcome: "error",
      error: String(err),
      latency_ms: Date.now() - start,
    });
    return Response.json({ ok: false, error: String(err) }, { status: 503 });
  }
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    if (req.method === "POST" && url.pathname === "/rpc") {
      return handleRpc(req, env);
    }
    if (req.method === "GET" && url.pathname === "/health") {
      return handleHealth(env);
    }
    return Response.json({ error: "not found" }, { status: 404 });
  },
};
