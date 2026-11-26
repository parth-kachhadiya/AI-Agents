import os
import json
import copy
import threading
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from dotenv import load_dotenv
from openai import OpenAI
from tools import TOOLS, TOOL_KIT


load_dotenv()

client = OpenAI(
    base_url = "https://openrouter.ai/api/v1",
    api_key  = os.environ["OPENROUTER_API_KEY"]
)

MODEL        = "openai/gpt-4o-mini"
CONTEXT_FILE = "json_files/02_context.json"

# ---------- Web UI settings ----------
UI_HOST = "127.0.0.1"
UI_PORT = 8765          # if busy, the next free port (up to +19) is used

# ---------- Pricing (edit these if the model or rates change) ----------
# gpt-4o-mini via OpenRouter: USD per 1 million tokens
PRICE_INPUT_PER_M  = 0.15
PRICE_OUTPUT_PER_M = 0.60
# Approximate exchange rate. Update it, or set USD_TO_INR in your .env
USD_TO_INR = 94.14

SYSTEM_PROMPT = {
    'role'    : 'system',
    'content' : 'You are a helpful assistant. Keep replies short.'
}

# Running totals for this session
total_input_tokens  = 0
total_output_tokens = 0
total_api_calls     = 0

# One entry per API call: {"call": n, "input": tokens, "output": tokens}
# (used by the chart in the web UI)
TOKEN_LOG = []


# =====================================================================
#  LIVE WEB UI  (standard library only, no extra packages needed)
# =====================================================================

# Shared state that the web page reads. Protected by a lock because the
# web server runs in a background thread.
STATE_LOCK = threading.Lock()
STATE = {
    "version"  : 0,
    "messages" : [],
    "status"   : "Starting...",
    "usage"    : {},
}


def publish_state(history):
    """Copy the current history + usage totals into the shared UI state."""
    snapshot = copy.deepcopy(history)
    usd, inr = calc_cost(total_input_tokens, total_output_tokens)
    with STATE_LOCK:
        STATE["messages"] = snapshot
        STATE["usage"] = {
            "model"         : MODEL,
            "context_file"  : CONTEXT_FILE,
            "input_tokens"  : total_input_tokens,
            "output_tokens" : total_output_tokens,
            "total_tokens"  : total_input_tokens + total_output_tokens,
            "api_calls"     : total_api_calls,
            "cost_usd"      : usd,
            "cost_inr"      : inr,
            "usd_to_inr"    : USD_TO_INR,
        }
        STATE["token_log"] = list(TOKEN_LOG)
        STATE["version"] += 1


def set_status(text):
    """Update the status line shown at the top of the web page."""
    with STATE_LOCK:
        STATE["status"] = text
        STATE["version"] += 1


UI_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Live Context Memory</title>
<style>
  :root {
    --bg:#f6f7f9; --card:#ffffff; --text:#1a1d21; --muted:#6b7280;
    --border:#e3e6ea; --code:#f1f3f5;
    --system:#6b7280; --user:#2563eb; --assistant:#059669; --tool:#d97706;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg:#0f1115; --card:#171a20; --text:#e6e8eb; --muted:#9aa3af;
      --border:#2a2f38; --code:#1f242c;
      --system:#9ca3af; --user:#60a5fa; --assistant:#34d399; --tool:#fbbf24;
    }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text);
         font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  header { position:sticky; top:0; z-index:5; background:var(--bg);
           border-bottom:1px solid var(--border); padding:12px 16px 10px; }
  .wrap { max-width:920px; margin:0 auto; }
  .top { display:flex; justify-content:space-between; align-items:center; gap:12px; }
  h1 { font-size:18px; margin:0; }
  .conn { display:flex; align-items:center; gap:6px; font-size:13px; color:var(--muted); }
  .dot { width:9px; height:9px; border-radius:50%; background:#9ca3af; }
  .dot.on  { background:#22c55e; box-shadow:0 0 0 3px rgba(34,197,94,.25); }
  .dot.off { background:#ef4444; }
  .sub { font-size:12.5px; color:var(--muted); margin-top:2px; }
  .status { margin-top:8px; font-size:13px; padding:6px 10px; border-radius:6px;
            background:var(--card); border:1px solid var(--border); }
  .stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(125px,1fr));
           gap:8px; margin-top:10px; }
  .stat { background:var(--card); border:1px solid var(--border); border-radius:8px;
          padding:8px 10px; }
  .stat .k { font-size:11.5px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
  .stat .v { font-size:17px; font-weight:600; margin-top:2px; font-variant-numeric:tabular-nums; }
  .toolbar { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-top:10px; font-size:13px; }
  .tabs button { border:1px solid var(--border); background:var(--card); color:var(--text);
                 padding:5px 12px; cursor:pointer; font-size:13px; }
  .tabs button:first-child { border-radius:6px 0 0 6px; }
  .tabs button:last-child  { border-radius:0 6px 6px 0; border-left:none; }
  .tabs button.active { background:var(--user); border-color:var(--user); color:#fff; }
  .muted { color:var(--muted); }
  .spacer { flex:1; }
  main { max-width:920px; margin:0 auto; padding:6px 16px 0; }

  .msg { --accent:var(--system); background:var(--card); border:1px solid var(--border);
         border-left:4px solid var(--accent); border-radius:8px; padding:10px 12px; margin:10px 0; }
  .msg.system    { --accent:var(--system); }
  .msg.user      { --accent:var(--user); }
  .msg.assistant { --accent:var(--assistant); }
  .msg.tool      { --accent:var(--tool); }
  .msg.fresh { animation: pop .5s ease-out; }
  @keyframes pop {
    from { opacity:0; transform:translateY(8px); box-shadow:0 0 0 2px var(--accent); }
    to   { opacity:1; transform:none; box-shadow:0 0 0 0 transparent; }
  }
  .msg-head { display:flex; align-items:center; gap:8px; margin-bottom:6px; font-size:12px; }
  .idx  { color:var(--muted); font-variant-numeric:tabular-nums; }
  .role { color:var(--accent); font-weight:700; text-transform:uppercase; letter-spacing:.05em; }
  .meta { color:var(--muted); font-family:ui-monospace,Menlo,Consolas,monospace; font-size:11.5px; }
  .body { white-space:pre-wrap; word-break:break-word; line-height:1.5; font-size:14.5px; }
  pre.code { background:var(--code); border-radius:6px; padding:8px 10px; margin:6px 0 0;
             font-family:ui-monospace,Menlo,Consolas,monospace; font-size:12.5px;
             white-space:pre-wrap; word-break:break-word; overflow-x:auto; }
  .tool-call { margin-top:8px; border:1px dashed var(--tool); border-radius:6px; padding:6px 8px; }
  .tc-head { display:flex; align-items:center; gap:8px; }
  .fn { color:var(--tool); font-weight:700; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:13px; }
  .raw { margin:10px 0; }

  /* ---- Token chart dock (pinned to the bottom of the window) ---- */
  .dock { position:sticky; bottom:0; z-index:4; background:var(--card);
          border:1px solid var(--border); border-bottom:none; border-radius:10px 10px 0 0;
          padding:10px 14px 6px; margin-top:16px; box-shadow:0 -6px 16px rgba(0,0,0,.08); }
  .dock-head { display:flex; flex-wrap:wrap; align-items:center; gap:12px; margin-bottom:4px; }
  .dock-head h2 { font-size:14px; margin:0; }
  .legend { display:flex; gap:14px; font-size:12.5px; color:var(--muted); }
  .lg { display:inline-block; width:14px; height:3px; border-radius:2px; margin-right:5px; vertical-align:middle; }
  .lg.in  { background:var(--user); }
  .lg.out { background:var(--assistant); }
  .mini { border:1px solid var(--border); background:var(--card); color:var(--text);
          border-radius:6px; padding:3px 10px; cursor:pointer; font-size:12.5px; }
  .dock.collapsed #chart, .dock.collapsed .modes, .dock.collapsed .legend { display:none; }
  .dock.collapsed .dock-head { margin-bottom:0; }
  #chart svg { width:100%; height:auto; display:block; }
  .empty { padding:14px 0 18px; font-size:13px; }
  .ax   { fill:var(--muted); font-size:11px; font-family:system-ui,sans-serif; }
  .grid { stroke:var(--border); stroke-width:1; }
  .line-in  { fill:none; stroke:var(--user);      stroke-width:2.5; stroke-linejoin:round; }
  .line-out { fill:none; stroke:var(--assistant); stroke-width:2.5; stroke-linejoin:round; }
  .pt-in  { fill:var(--user); }
  .pt-out { fill:var(--assistant); }
</style>
</head>
<body>
<header>
  <div class="wrap">
    <div class="top">
      <h1>Live Context Memory</h1>
      <div class="conn"><span id="dot" class="dot"></span><span id="conn">Connecting...</span></div>
    </div>
    <div class="sub"><span id="model">-</span> &middot; <span id="file">-</span></div>
    <div id="status" class="status">-</div>

    <div class="stats">
      <div class="stat"><div class="k">Input tokens</div><div class="v" id="s-in">0</div></div>
      <div class="stat"><div class="k">Output tokens</div><div class="v" id="s-out">0</div></div>
      <div class="stat"><div class="k">Total tokens</div><div class="v" id="s-total">0</div></div>
      <div class="stat"><div class="k">API calls</div><div class="v" id="s-calls">0</div></div>
      <div class="stat"><div class="k">Cost (USD)</div><div class="v" id="s-usd">$0</div></div>
      <div class="stat"><div class="k">Cost (INR)</div><div class="v" id="s-inr">0</div></div>
    </div>

    <div class="toolbar">
      <div class="tabs">
        <button id="tab-visual" class="active">Visual</button>
        <button id="tab-raw">Raw JSON</button>
      </div>
      <span id="count" class="muted"></span>
      <span id="roles" class="muted"></span>
      <span class="spacer"></span>
      <label><input type="checkbox" id="autoscroll" checked> Auto-scroll</label>
    </div>
  </div>
</header>

<main>
  <div id="list"></div>
  <pre id="raw" class="code raw" hidden></pre>

  <section id="dock" class="dock">
    <div class="dock-head">
      <h2>Token usage</h2>
      <div class="tabs modes">
        <button id="ch-call" class="active">Per API call</button>
        <button id="ch-cum">Cumulative</button>
      </div>
      <div class="legend">
        <span><i class="lg in"></i>Input</span>
        <span><i class="lg out"></i>Output</span>
      </div>
      <span class="spacer"></span>
      <button id="ch-toggle" class="mini">Hide</button>
    </div>
    <div id="chart"></div>
  </section>
</main>

<script>
(function () {
  const $ = (id) => document.getElementById(id);
  let lastVersion = -1;
  let lastCount = null;
  let view = "visual";
  let chartMode = "call";   // "call" = per API call, "cum" = cumulative
  let lastLog = [];

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function pretty(value) {
    if (typeof value !== "string") return JSON.stringify(value, null, 2);
    try { return JSON.stringify(JSON.parse(value), null, 2); }
    catch (e) { return value; }
  }

  function renderMessage(m, i, isNew) {
    const card = el("div", "msg " + m.role + (isNew ? " fresh" : ""));
    const head = el("div", "msg-head");
    head.appendChild(el("span", "idx", "#" + i));
    head.appendChild(el("span", "role", m.role));
    if (m.tool_call_id) head.appendChild(el("span", "meta", "id: " + m.tool_call_id));
    card.appendChild(head);

    if (m.content) {
      if (m.role === "tool") {
        card.appendChild(el("pre", "code", pretty(m.content)));
      } else {
        const text = typeof m.content === "string" ? m.content : JSON.stringify(m.content, null, 2);
        card.appendChild(el("div", "body", text));
      }
    }

    (m.tool_calls || []).forEach(function (tc) {
      const fn = tc.function || {};
      const box = el("div", "tool-call");
      const h = el("div", "tc-head");
      h.appendChild(el("span", "fn", (fn.name || "unknown") + "()"));
      h.appendChild(el("span", "meta", "id: " + (tc.id || "")));
      box.appendChild(h);
      box.appendChild(el("pre", "code", pretty(fn.arguments || "{}")));
      card.appendChild(box);
    });
    return card;
  }

  const fmt = (n) => (n || 0).toLocaleString();

  function render(s) {
    const u = s.usage || {};
    $("model").textContent = u.model || "-";
    $("file").textContent = u.context_file || "-";
    $("status").textContent = s.status || "";
    $("s-in").textContent = fmt(u.input_tokens);
    $("s-out").textContent = fmt(u.output_tokens);
    $("s-total").textContent = fmt(u.total_tokens);
    $("s-calls").textContent = fmt(u.api_calls);
    $("s-usd").textContent = "$" + (u.cost_usd || 0).toFixed(6);
    $("s-inr").textContent = "INR " + (u.cost_inr || 0).toFixed(4);

    const msgs = s.messages || [];
    $("count").textContent = msgs.length + " messages";
    const counts = {};
    msgs.forEach(function (m) { counts[m.role] = (counts[m.role] || 0) + 1; });
    $("roles").textContent = Object.keys(counts).map(function (k) { return k + " " + counts[k]; }).join(" \u00b7 ");

    const first = lastCount === null;
    const prev = first ? msgs.length : lastCount;

    const list = $("list");
    list.replaceChildren.apply(list, msgs.map(function (m, i) { return renderMessage(m, i, i >= prev); }));
    $("raw").textContent = JSON.stringify(msgs, null, 2);

    lastLog = s.token_log || [];
    drawChart();

    if ((first || msgs.length > prev) && $("autoscroll").checked) {
      window.scrollTo({ top: document.body.scrollHeight, behavior: first ? "auto" : "smooth" });
    }
    lastCount = msgs.length;
  }

  // ---------- Token line chart (plain SVG, no libraries) ----------
  function niceMax(v) {
    if (v <= 0) return 10;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    const f = v / p;
    const n = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
    return n * p;
  }

  function drawChart() {
    const host = $("chart");
    host.replaceChildren();
    const log = lastLog;
    if (!log.length) {
      host.appendChild(el("div", "muted empty", "No API calls yet. Send a message to see the chart."));
      return;
    }

    let ins = log.map(function (d) { return d.input; });
    let outs = log.map(function (d) { return d.output; });
    if (chartMode === "cum") {
      let a = 0, b = 0;
      ins = ins.map(function (v) { a += v; return a; });
      outs = outs.map(function (v) { b += v; return b; });
    }

    const NS = "http://www.w3.org/2000/svg";
    function mk(tag, attrs, text) {
      const e = document.createElementNS(NS, tag);
      for (const k in attrs) e.setAttribute(k, attrs[k]);
      if (text !== undefined) e.textContent = text;
      return e;
    }

    const W = 860, H = 190, L = 58, R = 16, T = 12, B = 34;
    const pw = W - L - R, ph = H - T - B;
    const n = log.length;
    const maxV = niceMax(Math.max.apply(null, ins.concat(outs)));
    const x = function (i) { return n === 1 ? L + pw / 2 : L + pw * i / (n - 1); };
    const y = function (v) { return T + ph - (v / maxV) * ph; };

    const svg = mk("svg", { viewBox: "0 0 " + W + " " + H, role: "img",
                            "aria-label": "Input and output tokens chart" });

    // horizontal grid lines + y-axis labels
    for (let t = 0; t <= 5; t++) {
      const v = maxV * t / 5, yy = y(v);
      svg.appendChild(mk("line", { x1: L, x2: W - R, y1: yy, y2: yy, "class": "grid" }));
      svg.appendChild(mk("text", { x: L - 8, y: yy + 4, "text-anchor": "end", "class": "ax" }, fmt(Math.round(v))));
    }

    // x-axis labels (API call numbers), thinned out if there are many
    const step = Math.max(1, Math.ceil(n / 10));
    log.forEach(function (d, i) {
      if (i % step === 0) {
        svg.appendChild(mk("text", { x: x(i), y: T + ph + 14, "text-anchor": "middle", "class": "ax" }, String(d.call)));
      }
    });
    svg.appendChild(mk("text", { x: L + pw / 2, y: H - 4, "text-anchor": "middle", "class": "ax" },
                       chartMode === "cum" ? "API call # (cumulative tokens)" : "API call #"));

    // lines
    function pts(a) {
      return a.map(function (v, i) { return x(i).toFixed(1) + "," + y(v).toFixed(1); }).join(" ");
    }
    svg.appendChild(mk("polyline", { points: pts(ins),  "class": "line-in" }));
    svg.appendChild(mk("polyline", { points: pts(outs), "class": "line-out" }));

    // points with hover tooltips
    const prefix = chartMode === "cum" ? "cumulative " : "";
    log.forEach(function (d, i) {
      const ci = mk("circle", { cx: x(i), cy: y(ins[i]), r: 4, "class": "pt-in" });
      ci.appendChild(mk("title", {}, "Call " + d.call + " - " + prefix + "input: " + fmt(ins[i]) + " tokens"));
      svg.appendChild(ci);
      const co = mk("circle", { cx: x(i), cy: y(outs[i]), r: 4, "class": "pt-out" });
      co.appendChild(mk("title", {}, "Call " + d.call + " - " + prefix + "output: " + fmt(outs[i]) + " tokens"));
      svg.appendChild(co);
    });

    host.appendChild(svg);
  }

  function setChartMode(m) {
    chartMode = m;
    $("ch-call").classList.toggle("active", m === "call");
    $("ch-cum").classList.toggle("active", m === "cum");
    drawChart();
  }

  function setConn(ok) {
    $("dot").className = "dot " + (ok ? "on" : "off");
    $("conn").textContent = ok ? "Live" : "Disconnected (program ended?)";
  }

  async function poll() {
    try {
      const r = await fetch("/api/state", { cache: "no-store" });
      const s = await r.json();
      setConn(true);
      if (s.version !== lastVersion) {
        lastVersion = s.version;
        render(s);
      }
    } catch (e) {
      setConn(false);
    }
  }

  function setView(v) {
    view = v;
    $("tab-visual").classList.toggle("active", v === "visual");
    $("tab-raw").classList.toggle("active", v === "raw");
    $("list").hidden = v !== "visual";
    $("raw").hidden = v !== "raw";
  }
  $("tab-visual").addEventListener("click", function () { setView("visual"); });
  $("tab-raw").addEventListener("click", function () { setView("raw"); });

  $("ch-call").addEventListener("click", function () { setChartMode("call"); });
  $("ch-cum").addEventListener("click", function () { setChartMode("cum"); });
  $("ch-toggle").addEventListener("click", function () {
    const collapsed = $("dock").classList.toggle("collapsed");
    this.textContent = collapsed ? "Show" : "Hide";
  });

  poll();
  setInterval(poll, 700);
})();
</script>
</body>
</html>
"""


class UIHandler(BaseHTTPRequestHandler):
    """Tiny HTTP handler: serves the page and the live state as JSON."""

    def log_message(self, format, *args):
        pass  # keep the terminal clean (no request logs)

    def _send(self, code, content_type, body):
        try:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            self._send(200, "text/html; charset=utf-8", UI_HTML.encode("utf-8"))
        elif path == "/api/state":
            with STATE_LOCK:
                body = json.dumps(STATE, ensure_ascii=False).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", body)
        else:
            self._send(404, "text/plain; charset=utf-8", b"Not found")


def start_ui():
    """Start the web server in a background thread and open the browser."""
    server = None
    port = UI_PORT
    for port in range(UI_PORT, UI_PORT + 20):
        try:
            server = ThreadingHTTPServer((UI_HOST, port), UIHandler)
            break
        except OSError:
            continue

    if server is None:
        print("[UI] Could not start the web UI (no free port). Chat continues without it.")
        return

    threading.Thread(target=server.serve_forever, daemon=True).start()

    url = f"http://{UI_HOST}:{port}"
    print(f"[UI] Live context viewer running at {url}")
    try:
        webbrowser.open(url)
    except Exception:
        print("[UI] Could not open the browser automatically. Open the link above manually.")


# =====================================================================
#  HELPERS
# =====================================================================
def save_context(history):
    """Write the current history to the JSON file (and refresh the web UI)."""
    with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    publish_state(history)


def load_context():
    """Load history from the JSON file. Returns None if missing or invalid."""
    if not os.path.exists(CONTEXT_FILE):
        return None
    try:
        with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and len(data) > 0 and data[0].get("role") == "system":
            return data
    except (json.JSONDecodeError, OSError, AttributeError):
        pass
    return None


def calc_cost(input_tokens, output_tokens):
    """Return (usd, inr) cost for the given token counts."""
    usd = (input_tokens / 1_000_000) * PRICE_INPUT_PER_M \
        + (output_tokens / 1_000_000) * PRICE_OUTPUT_PER_M
    return usd, usd * USD_TO_INR


def print_usage(label, input_tokens, output_tokens):
    usd, inr = calc_cost(input_tokens, output_tokens)
    print(
        f"[{label}] input: {input_tokens} | output: {output_tokens} | "
        f"total: {input_tokens + output_tokens} tokens | "
        f"cost: ${usd:.6f} / INR {inr:.4f}"
    )


def print_final_bill():
    usd, inr = calc_cost(total_input_tokens, total_output_tokens)
    in_usd  = (total_input_tokens  / 1_000_000) * PRICE_INPUT_PER_M
    out_usd = (total_output_tokens / 1_000_000) * PRICE_OUTPUT_PER_M

    print("\n" + "=" * 44)
    print("         FINAL BILL (this session)")
    print("=" * 44)
    print(f"Model           : {MODEL}")
    print(f"API calls       : {total_api_calls:>10}")
    print(f"Input tokens    : {total_input_tokens:>10}   (${in_usd:.6f})")
    print(f"Output tokens   : {total_output_tokens:>10}   (${out_usd:.6f})")
    print(f"Total tokens    : {total_input_tokens + total_output_tokens:>10}")
    print("-" * 44)
    print(f"Total cost (USD): ${usd:.6f}")
    print(f"Total cost (INR): INR {inr:.4f}  (rate: 1 USD = {USD_TO_INR})")
    print("=" * 44)


def run_turn(history):
    """
    Handle one user turn. The model may request tools, so this can involve
    several API calls: call -> run tools -> call again -> ... -> final answer.
    Returns (input_tokens, output_tokens) used during this turn.
    """
    global total_api_calls
    turn_in, turn_out = 0, 0

    while True:
        set_status("Waiting for the LLM to respond...")

        response = client.chat.completions.create(
            model      = MODEL,
            messages   = history,
            max_tokens = 400,
            tools      = TOOLS
        )
        total_api_calls += 1

        # Count tokens for this API call
        usage = response.usage
        call_in, call_out = 0, 0
        if usage:
            call_in  = usage.prompt_tokens or 0
            call_out = usage.completion_tokens or 0
        turn_in  += call_in
        turn_out += call_out

        # Log this call for the chart in the web UI
        TOKEN_LOG.append({
            "call"   : total_api_calls,
            "input"  : call_in,
            "output" : call_out,
        })

        # Debug: show the raw response
        print("-" * 40)
        print(response.model_dump_json(indent=2))
        print("-" * 40)

        choice = response.choices[0]
        msg    = choice.message

        history.append(msg.model_dump(exclude_none=True))
        save_context(history)

        # No tool requested -> this is the final answer
        if choice.finish_reason != "tool_calls" or not msg.tool_calls:
            print("\nASSISTANT :", msg.content or "")
            break

        # Run each requested tool and feed the result back
        for tool_object in msg.tool_calls:
            name = tool_object.function.name
            set_status(f"Running tool: {name}")
            try:
                arguments   = json.loads(tool_object.function.arguments)
                tool_result = TOOL_KIT[name](**arguments)
                print(f"\n[TOOL] {name}({arguments}) -> {tool_result}")
            except Exception as par_err:
                print(f"\n[TOOL-CALL-ERR] {name}: {par_err}")
                tool_result = {"error": str(par_err)}

            history.append(
                {
                    'role'         : 'tool',
                    'tool_call_id' : tool_object.id,
                    'content'      : json.dumps(tool_result)
                }
            )
        save_context(history)

    return turn_in, turn_out


# =====================================================================
#  STARTUP: continue or new?
# =====================================================================
HISTORY = None
saved   = load_context()

if saved is not None:
    print(f"Found a saved conversation in '{CONTEXT_FILE}' ({len(saved)} messages).")
    while True:
        choice = input("Continue it (c) or start a NEW conversation (n)? [c/n]: ").strip().lower()
        if choice in ('c', 'n'):
            break
        print("Please type 'c' or 'n'.")

    if choice == 'c':
        HISTORY = saved
        print("Continuing previous conversation.")
    else:
        print("Starting a new conversation (old one will be overwritten).")
else:
    print("No saved conversation found. Starting a new one.")

if HISTORY is None:
    HISTORY = [SYSTEM_PROMPT.copy()]

# Save immediately so the file reflects the chosen state
save_context(HISTORY)

# Start the live web UI (after the choice above, so it opens with the right data)
start_ui()

print("\nType 'exit' or 'quit' to end the chat and see the final bill.")

# =====================================================================
#  CHAT LOOP
# =====================================================================
try:
    while True:
        set_status("Waiting for your input...")
        user_input = input("\nUSER : ").strip()

        if user_input.lower() in ('exit', 'quit'):
            break

        if not user_input:
            continue

        # Remember where this turn started, so we can roll back on failure
        turn_start = len(HISTORY)

        HISTORY.append(
            {
                'role'    : 'user',
                'content' : user_input
            }
        )
        save_context(HISTORY)

        try:
            turn_in, turn_out = run_turn(HISTORY)
        except Exception as res_exc:
            print(f"\n[API-ERR] : {res_exc}")
            # Roll back the whole turn (user msg + any half-finished tool calls)
            # so we never leave a tool_call without its tool result.
            del HISTORY[turn_start:]
            save_context(HISTORY)
            continue

        total_input_tokens  += turn_in
        total_output_tokens += turn_out

        # Refresh the web UI so it shows the updated token/cost totals
        publish_state(HISTORY)

        print()
        print_usage("This turn    ", turn_in, turn_out)
        print_usage("Session total", total_input_tokens, total_output_tokens)

except (KeyboardInterrupt, EOFError):
    print("\n\nInterrupted.")

# =====================================================================
#  QUIT: show final bill
# =====================================================================
set_status("Session ended")
print_final_bill()