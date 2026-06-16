export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const token = request.headers.get("Authorization") || "";

    if (url.pathname === "/health") {
      return json({ success: true, service: "sunflower-d1-state" });
    }

    if (!env.STATE_TOKEN || token !== `Bearer ${env.STATE_TOKEN}`) {
      return json({ success: false, error: "unauthorized" }, 401);
    }

    const match = url.pathname.match(/^\/state\/([^/]+)$/);
    if (!match) {
      return json({ success: false, error: "not_found" }, 404);
    }

    const key = decodeURIComponent(match[1]);
    if (!/^[a-z0-9_:-]{1,80}$/i.test(key)) {
      return json({ success: false, error: "bad_key" }, 400);
    }

    if (request.method === "GET") {
      const row = await env.DB.prepare("SELECT value FROM app_state WHERE key = ?")
        .bind(key)
        .first();
      if (!row) return json({ success: true, found: false, value: null });
      return json({ success: true, found: true, value: JSON.parse(row.value) });
    }

    if (request.method === "PUT") {
      const body = await request.json().catch(() => null);
      if (!body || !Object.prototype.hasOwnProperty.call(body, "value")) {
        return json({ success: false, error: "missing_value" }, 400);
      }
      await env.DB.prepare(
        "INSERT INTO app_state (key, value, updated_at) VALUES (?, ?, ?) " +
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at"
      ).bind(key, JSON.stringify(body.value), new Date().toISOString()).run();
      return json({ success: true });
    }

    return json({ success: false, error: "method_not_allowed" }, 405);
  }
};

function json(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}
