const OWNER = "raywari";
const REPO = "test";
const WORKFLOW = "update.yml";
const REF = "main";
const STATE_URL = `https://raw.githubusercontent.com/${OWNER}/${REPO}/${REF}/stream_state.json`;
const REFRESH_THRESHOLD_MS = 30 * 60 * 1000;
const MIN_COOLDOWN_AFTER_UPDATE_MS = 45 * 60 * 1000;

const STREAM_HEADERS = {
  "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  "Referer": "https://rutube.ru/",
};

function parseExpiryFromUrl(url) {
  if (!url) return null;
  const m = url.match(/\/(\d{10})\//);
  if (m) {
    const ts = parseInt(m[1], 10);
    if (!Number.isNaN(ts)) return ts * 1000;
  }
  const eMatch = url.match(/[?&]e=(\d+)/);
  if (eMatch) {
    const ts = parseInt(eMatch[1], 10);
    if (!Number.isNaN(ts)) return ts * 1000;
  }
  return null;
}

async function fetchState() {
  const res = await fetch(`${STATE_URL}?t=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) return null;
  return await res.json();
}

async function isStreamAlive(url) {
  if (!url) return false;
  try {
    const res = await fetch(url, { method: "HEAD", headers: STREAM_HEADERS });
    return res.ok;
  } catch (e) {
    try {
      const res = await fetch(url, { headers: STREAM_HEADERS });
      return res.ok;
    } catch (e2) {
      return false;
    }
  }
}

async function triggerRefresh(env) {
  const token = env.GH_TOKEN;
  if (!token) {
    throw new Error("GH_TOKEN secret is not configured");
  }
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Accept": "application/vnd.github+json",
      "User-Agent": "rutube-refresh-worker",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({ ref: REF }),
  });
  if (res.status !== 204) {
    const text = await res.text();
    throw new Error(`GitHub dispatch failed: ${res.status} ${text}`);
  }
  return true;
}

async function checkAndRefresh(env) {
  const state = await fetchState();
  let needsRefresh = false;
  let reason = "";

  if (!state) {
    needsRefresh = true;
    reason = "state missing";
  } else {
    const now = Date.now();
    const expiry = state.expires_at ? state.expires_at * 1000 : null;
    const urlExpiry = state.url_expiry ? state.url_expiry * 1000 : null;
    const effectiveExpiry = expiry && urlExpiry ? Math.min(expiry, urlExpiry) : (expiry || urlExpiry);

    const streamUrl = state?.urls?.["720p"] || state?.url_720p;
    const alive = await isStreamAlive(streamUrl);
    const lastUpdatedAt = state.updated_at ? state.updated_at * 1000 : null;

    if (effectiveExpiry && now >= effectiveExpiry - REFRESH_THRESHOLD_MS) {
      needsRefresh = true;
      reason = "expiring soon";
    } else if (streamUrl) {
      const parsed = parseExpiryFromUrl(streamUrl);
      if (parsed && now >= parsed - REFRESH_THRESHOLD_MS) {
        needsRefresh = true;
        reason = "url expiring soon";
      } else if (!alive) {
        if (lastUpdatedAt && (now - lastUpdatedAt < MIN_COOLDOWN_AFTER_UPDATE_MS)) {
          return {
            refreshed: false,
            reason: `stream not alive but updated recently (${Math.round((now - lastUpdatedAt) / 60000)}m ago, cooldown ${MIN_COOLDOWN_AFTER_UPDATE_MS / 60000}m)`
          };
        }
        needsRefresh = true;
        reason = "stream not alive";
      }
    } else if (!alive) {
      if (lastUpdatedAt && (now - lastUpdatedAt < MIN_COOLDOWN_AFTER_UPDATE_MS)) {
        return {
          refreshed: false,
          reason: `stream not alive but updated recently (${Math.round((now - lastUpdatedAt) / 60000)}m ago, cooldown ${MIN_COOLDOWN_AFTER_UPDATE_MS / 60000}m)`
        };
      }
      needsRefresh = true;
      reason = "stream not alive";
    }
  }

  if (needsRefresh) {
    await triggerRefresh(env);
    return { refreshed: true, reason };
  }
  return { refreshed: false, reason: "ok" };
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(checkAndRefresh(env).catch((e) => {
      console.error("scheduled error:", e?.message || e);
    }));
  },
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/check") {
      try {
        const result = await checkAndRefresh(env);
        return new Response(JSON.stringify(result), { headers: { "content-type": "application/json" } });
      } catch (e) {
        return new Response(JSON.stringify({ error: e?.message || String(e) }), { status: 500, headers: { "content-type": "application/json" } });
      }
    }
    return new Response("rutube-refresh-worker ok", { status: 200 });
  },
};
