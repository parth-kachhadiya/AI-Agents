"""
jsonl_side_by_side.py  (v2)

Compare up to 5 JSON objects from a .jsonl file side-by-side in the browser.

Improvements:
  - Resizable columns (drag handles + width slider)
  - Nested / hierarchical comparison (tree view)
  - Long property names handled cleanly (no overlapping)
"""

import json
import sys
import webbrowser
from pathlib import Path
from html import escape
from typing import Any


def load_jsonl(path: str, max_objects: int = 5) -> list[dict]:
    objects = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    print(f"Warning: line {i} is not a JSON object (dict), skipping.")
                    continue
                objects.append(obj)
                if len(objects) >= max_objects:
                    break
            except json.JSONDecodeError as e:
                print(f"Error parsing line {i}: {e}")
    return objects


def is_equal(a: Any, b: Any) -> bool:
    """Deep equality that treats missing as different."""
    try:
        return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
    except Exception:
        return a == b


def collect_all_keys_nested(objects: list[Any], path: str = "") -> set[str]:
    """Recursively collect every possible dotted path that appears in any object."""
    keys: set[str] = set()
    if not objects:
        return keys

    # Find all keys present at this level across objects
    all_level_keys: set[str] = set()
    for obj in objects:
        if isinstance(obj, dict):
            all_level_keys.update(obj.keys())
        elif isinstance(obj, list):
            # For lists we use indices
            for i in range(max((len(o) for o in objects if isinstance(o, list)), default=0)):
                all_level_keys.add(str(i))

    for key in sorted(all_level_keys, key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else 0, x)):
        full_path = f"{path}.{key}" if path else key
        keys.add(full_path)

        children = []
        for obj in objects:
            if isinstance(obj, dict):
                children.append(obj.get(key))
            elif isinstance(obj, list) and key.isdigit():
                idx = int(key)
                children.append(obj[idx] if idx < len(obj) else None)
            else:
                children.append(None)

        # Recurse only if at least one child is dict or list
        if any(isinstance(c, (dict, list)) for c in children):
            keys.update(collect_all_keys_nested(children, full_path))

    return keys


def get_value_at_path(obj: Any, path: str) -> Any:
    """Navigate to a dotted path. Returns a sentinel if missing."""
    if path == "":
        return obj
    parts = path.split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                return _MISSING
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            if idx >= len(current):
                return _MISSING
            current = current[idx]
        else:
            return _MISSING
    return current


_MISSING = object()


def value_to_display(v: Any) -> str:
    if v is _MISSING:
        return "—"
    if isinstance(v, (dict, list)):
        # Show a short summary for complex values in the tree
        if isinstance(v, dict):
            return f"{{… {len(v)} keys}}"
        return f"[… {len(v)} items]"
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return v
    return str(v)


def generate_html(objects: list[dict], title: str = "JSONL Side-by-Side Comparison") -> str:
    n = len(objects)
    all_paths = sorted(collect_all_keys_nested(objects), key=lambda p: [int(x) if x.isdigit() else x for x in p.split(".")])

    # Determine which paths differ
    differing: set[str] = set()
    for path in all_paths:
        vals = [get_value_at_path(obj, path) for obj in objects]
        # Compare pairwise
        first = vals[0]
        for v in vals[1:]:
            if not is_equal(first, v):
                differing.add(path)
                break
            # Also mark if any is missing while others exist
            if (first is _MISSING) != (v is _MISSING):
                differing.add(path)
                break

    # Build tree rows with depth
    rows_html = []
    for path in all_paths:
        depth = path.count(".")
        key_name = path.split(".")[-1]
        is_diff = path in differing

        # Indentation visual
        indent = "&nbsp;" * (depth * 4)
        prefix = "└─ " if depth > 0 else ""

        row_class = ' class="diff"' if is_diff else ""
        cells = [
            f'<td class="key" title="{escape(path)}">'
            f'<span class="indent">{indent}{prefix}</span>'
            f'<span class="key-name">{escape(key_name)}</span>'
            f'</td>'
        ]

        for obj in objects:
            val = get_value_at_path(obj, path)
            display = escape(value_to_display(val))
            full_title = escape(json.dumps(val, ensure_ascii=False, default=str) if val is not _MISSING else "—")
            cell_class = ' class="diff-cell"' if is_diff else ""
            cells.append(
                f'<td{cell_class} title="{full_title}">'
                f'<div class="cell-content">{display}</div>'
                f'</td>'
            )

        rows_html.append(f"<tr{row_class} data-path=\"{escape(path)}\">{''.join(cells)}</tr>")

    headers = ["<th class=\"key-header\">Property</th>"] + [
        f'<th class="obj-header" data-col="{i}">Object {i+1}<span class="resize-handle"></span></th>'
        for i in range(n)
    ]

    # Raw JSON cards
    raw_cards = ""
    for i, obj in enumerate(objects):
        pretty = escape(json.dumps(obj, indent=2, ensure_ascii=False))
        raw_cards += f"""
      <div class="raw-card" data-col="{i}">
        <div class="raw-header">
          <h3>Object {i+1}</h3>
          <div class="raw-controls">
            <button onclick="adjustColWidth({i}, -40)" title="Narrower">−</button>
            <button onclick="adjustColWidth({i}, 40)" title="Wider">+</button>
          </div>
        </div>
        <pre>{pretty}</pre>
      </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
  :root {{
    --bg: #0f1117;
    --card: #1a1d27;
    --border: #2d3348;
    --text: #e2e8f0;
    --muted: #94a3b8;
    --accent: #38bdf8;
    --diff-bg: #3b1f1f;
    --diff-border: #ef4444;
    --key-bg: #151821;
    --col-width: 280px;          /* default object column width */
    --key-width: 260px;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 16px 20px 40px;
    line-height: 1.45;
  }}

  h1 {{
    font-size: 1.4rem;
    margin-bottom: 6px;
    color: var(--accent);
  }}

  .meta {{
    color: var(--muted);
    margin-bottom: 14px;
    font-size: 0.88rem;
  }}

  /* ===== Controls ===== */
  .controls {{
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    align-items: center;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 18px;
  }}

  .controls label {{
    font-size: 0.85rem;
    color: var(--muted);
    display: flex;
    align-items: center;
    gap: 8px;
  }}

  .controls input[type="range"] {{
    width: 140px;
    accent-color: var(--accent);
  }}

  .controls button {{
    background: #252a3a;
    border: 1px solid var(--border);
    color: var(--text);
    padding: 5px 12px;
    border-radius: 5px;
    cursor: pointer;
    font-size: 0.85rem;
  }}
  .controls button:hover {{
    background: #2f364a;
    border-color: var(--accent);
  }}

  .legend {{
    font-size: 0.82rem;
    color: var(--muted);
  }}
  .legend span {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    background: var(--diff-bg);
    border: 1px solid var(--diff-border);
    margin-right: 6px;
    color: #fca5a5;
  }}

  /* ===== Table ===== */
  .table-wrapper {{
    overflow: auto;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--card);
    max-height: 70vh;
  }}

  table {{
    border-collapse: separate;
    border-spacing: 0;
    width: max-content;
    min-width: 100%;
  }}

  th, td {{
    border-bottom: 1px solid var(--border);
    border-right: 1px solid var(--border);
    padding: 8px 12px;
    vertical-align: top;
    text-align: left;
  }}

  th {{
    background: var(--key-bg);
    position: sticky;
    top: 0;
    z-index: 20;
    color: var(--accent);
    font-weight: 600;
    font-size: 0.9rem;
    white-space: nowrap;
  }}

  /* Sticky first column (keys) */
  th.key-header,
  td.key {{
    position: sticky;
    left: 0;
    z-index: 15;
    background: var(--key-bg);
    min-width: var(--key-width);
    max-width: var(--key-width);
    width: var(--key-width);
  }}
  th.key-header {{
    z-index: 30;
  }}

  td.key {{
    font-family: ui-monospace, 'Cascadia Code', 'Fira Code', 'SF Mono', monospace;
    font-size: 0.8rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}

  .key-name {{
    color: #a5b4fc;
  }}
  .indent {{
    color: #475569;
    user-select: none;
  }}

  /* Object columns – width controlled by CSS variable */
  th.obj-header,
  td:not(.key) {{
    min-width: var(--col-width);
    max-width: var(--col-width);
    width: var(--col-width);
  }}

  td:not(.key) {{
    font-family: ui-monospace, 'Cascadia Code', 'Fira Code', 'SF Mono', monospace;
    font-size: 0.8rem;
  }}

  .cell-content {{
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }}

  /* Diff highlighting */
  tr.diff {{
    background: var(--diff-bg);
  }}
  tr.diff td.key {{
    background: #2a1515;
  }}
  td.diff-cell {{
    border-left: 3px solid var(--diff-border);
  }}

  /* Resize handle on headers */
  th.obj-header {{
    position: relative;
    user-select: none;
  }}
  .resize-handle {{
    position: absolute;
    top: 0;
    right: 0;
    width: 6px;
    height: 100%;
    cursor: col-resize;
    background: transparent;
  }}
  .resize-handle:hover,
  .resize-handle.active {{
    background: var(--accent);
  }}

  /* ===== Raw JSON section ===== */
  .raw-section {{
    margin-top: 36px;
  }}
  .raw-section h2 {{
    font-size: 1.15rem;
    margin-bottom: 12px;
    color: var(--accent);
  }}

  .raw-grid {{
    display: grid;
    grid-template-columns: repeat({n}, minmax(200px, 1fr));
    gap: 12px;
  }}

  .raw-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    min-width: 0; /* important for grid overflow */
  }}

  .raw-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--key-bg);
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
  }}
  .raw-header h3 {{
    font-size: 0.9rem;
    color: var(--accent);
  }}
  .raw-controls button {{
    background: #252a3a;
    border: 1px solid var(--border);
    color: var(--text);
    width: 28px;
    height: 24px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
    line-height: 1;
  }}
  .raw-controls button:hover {{
    background: #2f364a;
  }}

  .raw-card pre {{
    padding: 12px;
    margin: 0;
    font-size: 0.75rem;
    overflow: auto;
    max-height: 420px;
    white-space: pre-wrap;
    word-break: break-word;
    flex: 1;
  }}

  @media (max-width: 1100px) {{
    .raw-grid {{ grid-template-columns: 1fr 1fr; }}
  }}
  @media (max-width: 640px) {{
    .raw-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
  <h1>{escape(title)}</h1>
  <div class="meta">
    Showing <strong>{n}</strong> object(s) ·
    <strong>{len(all_paths)}</strong> paths ·
    <strong style="color:#f87171">{len(differing)}</strong> differences
  </div>

  <div class="controls">
    <label>
      Column width
      <input type="range" id="colWidthSlider" min="160" max="600" value="280"
             oninput="setColWidth(this.value)">
      <span id="colWidthValue">280px</span>
    </label>

    <label>
      Key column
      <input type="range" id="keyWidthSlider" min="140" max="450" value="260"
             oninput="setKeyWidth(this.value)">
      <span id="keyWidthValue">260px</span>
    </label>

    <button onclick="resetWidths()">Reset widths</button>
    <button onclick="toggleOnlyDiffs()" id="diffToggle">Show only differences</button>

    <div class="legend">
      <span>red rows</span> = values differ at this path
    </div>
  </div>

  <div class="table-wrapper" id="tableWrapper">
    <table id="cmpTable">
      <thead>
        <tr>{''.join(headers)}</tr>
      </thead>
      <tbody>
        {''.join(rows_html)}
      </tbody>
    </table>
  </div>

  <div class="raw-section">
    <h2>Raw JSON (pretty-printed)</h2>
    <div class="raw-grid" id="rawGrid">
      {raw_cards}
    </div>
  </div>

<script>
  // ---- Width controls ----
  function setColWidth(px) {{
    document.documentElement.style.setProperty('--col-width', px + 'px');
    document.getElementById('colWidthValue').textContent = px + 'px';
    document.getElementById('colWidthSlider').value = px;
  }}

  function setKeyWidth(px) {{
    document.documentElement.style.setProperty('--key-width', px + 'px');
    document.getElementById('keyWidthValue').textContent = px + 'px';
    document.getElementById('keyWidthSlider').value = px;
  }}

  function adjustColWidth(colIndex, delta) {{
    // This adjusts the CSS variable (all object columns stay equal)
    // For per-column we would need more complex logic; for simplicity we keep them synced
    const current = parseInt(getComputedStyle(document.documentElement)
                             .getPropertyValue('--col-width'));
    setColWidth(Math.max(160, Math.min(700, current + delta)));
  }}

  function resetWidths() {{
    setColWidth(280);
    setKeyWidth(260);
  }}

  // ---- Show only differences ----
  let showingOnlyDiffs = false;
  function toggleOnlyDiffs() {{
    showingOnlyDiffs = !showingOnlyDiffs;
    const rows = document.querySelectorAll('#cmpTable tbody tr');
    rows.forEach(r => {{
      if (showingOnlyDiffs) {{
        r.style.display = r.classList.contains('diff') ? '' : 'none';
      }} else {{
        r.style.display = '';
      }}
    }});
    document.getElementById('diffToggle').textContent =
      showingOnlyDiffs ? 'Show all rows' : 'Show only differences';
  }}

  // ---- Column resize by dragging the handle ----
  (function enableResize() {{
    const table = document.getElementById('cmpTable');
    let startX, startWidth, handle;

    document.querySelectorAll('.resize-handle').forEach(h => {{
      h.addEventListener('mousedown', e => {{
        e.preventDefault();
        handle = h;
        handle.classList.add('active');
        startX = e.clientX;
        startWidth = parseInt(getComputedStyle(document.documentElement)
                              .getPropertyValue('--col-width'));
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
      }});
    }});

    function onMouseMove(e) {{
      if (!handle) return;
      const dx = e.clientX - startX;
      setColWidth(Math.max(160, Math.min(700, startWidth + dx)));
    }}

    function onMouseUp() {{
      if (handle) handle.classList.remove('active');
      handle = null;
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    }}
  }})();
</script>
</body>
</html>"""
    return html


def main():
    if len(sys.argv) < 2:
        print("Usage: python jsonl_side_by_side.py <file.jsonl> [output.html]")
        print("Example: python jsonl_side_by_side.py data.jsonl")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"File not found: {input_path}")
        sys.exit(1)

    objects = load_jsonl(str(input_path), max_objects=5)
    if not objects:
        print("No valid JSON objects found.")
        sys.exit(1)

    print(f"Loaded {len(objects)} object(s) from {input_path}")

    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("comparison.html")
    html = generate_html(objects, title=f"Comparison · {input_path.name}")
    output_path.write_text(html, encoding="utf-8")
    print(f"HTML written to: {output_path.resolve()}")

    webbrowser.open(output_path.resolve().as_uri())
    print("Opened in browser.")


if __name__ == "__main__":
    main()