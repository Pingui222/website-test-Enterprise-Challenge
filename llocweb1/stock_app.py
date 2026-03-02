"""
Stock Manager Flask App
Integrates PyCode.py (MySQL stock DB) and CwithPy.py (Arduino serial weight reader)
"""

from flask import Flask, render_template_string, request, jsonify, redirect, url_for
import mysql.connector
from datetime import datetime
import re
import serial
import time

app = Flask(__name__)

# ─── CONFIG ──────────────────────────────────────────────────────────────────

dades_base_dades = {
    "host": "localhost",
    "user": "root",
    "password": "engicontrasenya702406?",
    "database": "printing_shop"
}

codi_colors = {
    "R": "Red", "G": "Green", "B": "Blue", "Y": "Yellow",
    "K": "Black", "W": "White", "C": "Cyan", "M": "Magenta",
}

# Arduino / Serial config — adjust port as needed
SERIAL_PORT = "Port4"   # e.g. "COM3" on Windows, "/dev/ttyUSB0" on Linux
BAUD_RATE   = 115200
TIMEOUT     = 0.1

# ─── DB HELPERS (from PyCode.py) ─────────────────────────────────────────────

def get_connection():
    return mysql.connector.connect(**dades_base_dades)


def setup_database():
    config = {k: v for k, v in dades_base_dades.items() if k != "database"}
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {dades_base_dades['database']}")
    cursor.execute(f"USE {dades_base_dades['database']}")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            item_id      VARCHAR(20) PRIMARY KEY,
            colour       CHAR(20)   NOT NULL,
            is_in_stock  BOOLEAN    NOT NULL DEFAULT TRUE,
            weight_g     VARCHAR(4) NOT NULL,
            notes        TEXT,
            arrival_date DATE       NOT NULL
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()


def generar_id(colour_code: str, number: int, arrival_date: datetime) -> str:
    colour_code = colour_code.upper()
    if colour_code not in codi_colors:
        raise ValueError(f"Invalid colour: {colour_code}")
    return f"{colour_code}{number:04d}{arrival_date.strftime('%d%m%Y')}"


def add_item(colour_code, number, arrival_date, weight_g, is_in_stock=True, notes=""):
    item_id = generar_id(colour_code, number, arrival_date)
    colour_name = codi_colors[colour_code.upper()]
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO stock (item_id, colour, is_in_stock, weight_g, notes, arrival_date)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (item_id, colour_name, is_in_stock, weight_g, notes, arrival_date.date()))
        conn.commit()
        return item_id, None
    except mysql.connector.IntegrityError:
        return None, "Item already exists."
    finally:
        cursor.close()
        conn.close()


def search_items(item_id=None, colour=None, in_stock=None, min_weight=None, max_weight=None):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    q = "SELECT * FROM stock WHERE 1=1"
    params = []
    if item_id:
        q += " AND item_id = %s"; params.append(item_id)
    if colour:
        if len(colour) == 1:
            colour = codi_colors.get(colour.upper(), colour)
        q += " AND colour = %s"; params.append(colour)
    if in_stock is not None:
        q += " AND is_in_stock = %s"; params.append(in_stock)
    if min_weight is not None:
        q += " AND weight_g >= %s"; params.append(min_weight)
    if max_weight is not None:
        q += " AND weight_g <= %s"; params.append(max_weight)
    cursor.execute(q, params)
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results


def update_item(item_id, is_in_stock=None, weight_g=None, notes=None):
    updates, params = [], []
    if is_in_stock is not None:
        updates.append("is_in_stock = %s"); params.append(is_in_stock)
        if not is_in_stock:
            updates.append("weight_g = %s"); params.append(0)
    if weight_g is not None:
        updates.append("weight_g = %s"); params.append(weight_g)
    if notes is not None:
        updates.append("notes = %s"); params.append(notes)
    if not updates:
        return 0
    params.append(item_id)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE stock SET {', '.join(updates)} WHERE item_id = %s", params)
    conn.commit()
    rows = cursor.rowcount
    cursor.close()
    conn.close()
    return rows


def delete_item(item_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM stock WHERE item_id = %s", (item_id,))
    conn.commit()
    rows = cursor.rowcount
    cursor.close()
    conn.close()
    return rows

# ─── ARDUINO / SERIAL HELPER (from CwithPy.py) ───────────────────────────────

def read_weight_from_arduino(x=10):
    """
    Opens a serial connection to the Arduino, requests weight data,
    reads the response and returns it as a float (grams).
    Returns None on any error.
    """
    try:
        arduino = serial.Serial(port=SERIAL_PORT, baudrate=BAUD_RATE, timeout=TIMEOUT)
        arduino.write(bytes(str(x), 'utf-8'))
        time.sleep(0.05)
        raw = arduino.readline()
        arduino.close()
        weight = float(raw.decode('utf-8').strip())
        return weight
    except Exception as e:
        app.logger.error(f"Serial error: {e}")
        return None

# ─── ROUTES ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    items = search_items()
    # serialise dates for template
    for item in items:
        if hasattr(item.get('arrival_date'), 'strftime'):
            item['arrival_date'] = item['arrival_date'].strftime('%d/%m/%Y')
    return render_template_string(HTML_TEMPLATE,
                                  items=items,
                                  colours=codi_colors,
                                  msg=request.args.get('msg'),
                                  err=request.args.get('err'))


@app.route('/api/read_weight', methods=['GET'])
def api_read_weight():
    """AJAX endpoint — reads live weight from Arduino."""
    weight = read_weight_from_arduino()
    if weight is None:
        return jsonify({"ok": False, "error": "Could not read from Arduino. Check serial port."})
    return jsonify({"ok": True, "weight": weight})


@app.route('/add', methods=['POST'])
def add():
    try:
        colour   = request.form['colour'].strip().upper()
        number   = int(request.form['number'])
        date_str = request.form['arrival_date'].strip()
        arrival  = datetime.strptime(date_str, "%d/%m/%Y")
        notes    = request.form.get('notes', '').strip()
        in_stock = request.form.get('in_stock') == 'on'

        # Weight: prefer Arduino reading if requested, else manual input
        use_arduino = request.form.get('use_arduino') == 'on'
        if use_arduino:
            weight = read_weight_from_arduino()
            if weight is None:
                return redirect(url_for('index', err="Arduino not reachable — enter weight manually."))
        else:
            weight = float(request.form['weight_g'])

        item_id, error = add_item(colour, number, arrival, weight, in_stock, notes)
        if error:
            return redirect(url_for('index', err=error))
        return redirect(url_for('index', msg=f"Item {item_id} added successfully."))
    except Exception as e:
        return redirect(url_for('index', err=str(e)))


@app.route('/update', methods=['POST'])
def update():
    item_id  = request.form['item_id'].strip()
    stock_v  = request.form.get('is_in_stock', '')
    in_stock = True if stock_v == 'y' else (False if stock_v == 'n' else None)
    weight   = request.form.get('weight_g', '').strip()
    notes    = request.form.get('notes', '').strip() or None
    rows = update_item(item_id, is_in_stock=in_stock,
                       weight_g=float(weight) if weight else None, notes=notes)
    msg = f"Updated {rows} item(s)." if rows else f"Item '{item_id}' not found."
    return redirect(url_for('index', msg=msg))


@app.route('/delete/<item_id>', methods=['POST'])
def delete(item_id):
    rows = delete_item(item_id)
    msg = f"Deleted '{item_id}'." if rows else f"Item '{item_id}' not found."
    return redirect(url_for('index', msg=msg))


@app.route('/search')
def search():
    item_id   = request.args.get('item_id') or None
    colour    = request.args.get('colour') or None
    stock_v   = request.args.get('in_stock', '')
    in_stock  = True if stock_v == 'y' else (False if stock_v == 'n' else None)
    min_w     = request.args.get('min_weight', '')
    max_w     = request.args.get('max_weight', '')
    items = search_items(
        item_id=item_id, colour=colour, in_stock=in_stock,
        min_weight=float(min_w) if min_w else None,
        max_weight=float(max_w) if max_w else None
    )
    for item in items:
        if hasattr(item.get('arrival_date'), 'strftime'):
            item['arrival_date'] = item['arrival_date'].strftime('%d/%m/%Y')
    return render_template_string(HTML_TEMPLATE,
                                  items=items,
                                  colours=codi_colors,
                                  msg=None, err=None,
                                  search_active=True)

# ─── HTML TEMPLATE ────────────────────────────────────────────────────────────

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Manager — EngiConsulting</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet">
<style>
  :root {
    --ink:   #0f0f0f;
    --paper: #f5f0e8;
    --acc:   #e84b1a;
    --acc2:  #1a6ce8;
    --muted: #9a9080;
    --card:  #ffffff;
    --border:#d8d0c0;
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Space Mono', monospace;
    background: var(--paper);
    color: var(--ink);
    min-height: 100vh;
  }

  /* ── HEADER ── */
  header {
    background: var(--ink);
    color: var(--paper);
    padding: 1.2rem 2rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    border-bottom: 4px solid var(--acc);
  }
  header h1 {
    font-family: 'Syne', sans-serif;
    font-size: 1.5rem;
    font-weight: 800;
    letter-spacing: -0.02em;
  }
  header .badge {
    font-size: 0.65rem;
    background: var(--acc);
    color: #fff;
    padding: 0.2rem 0.5rem;
    border-radius: 2px;
    letter-spacing: 0.08em;
  }

  /* ── LAYOUT ── */
  .page { display: grid; grid-template-columns: 320px 1fr; min-height: calc(100vh - 68px); }

  /* ── SIDEBAR ── */
  aside {
    background: var(--card);
    border-right: 2px solid var(--border);
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }
  .panel-title {
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 0.75rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.4rem;
    margin-bottom: 0.5rem;
  }

  /* ── FORMS ── */
  label { font-size: 0.72rem; color: var(--muted); display: block; margin-bottom: 0.2rem; }
  input[type=text], input[type=number], input[type=date],
  select, textarea {
    width: 100%;
    padding: 0.45rem 0.6rem;
    border: 1.5px solid var(--border);
    border-radius: 3px;
    font-family: 'Space Mono', monospace;
    font-size: 0.78rem;
    background: var(--paper);
    color: var(--ink);
    margin-bottom: 0.7rem;
    transition: border-color 0.15s;
  }
  input:focus, select:focus, textarea:focus {
    outline: none;
    border-color: var(--acc2);
  }
  .checkbox-row {
    display: flex; align-items: center; gap: 0.5rem;
    margin-bottom: 0.7rem;
    font-size: 0.78rem;
  }
  .checkbox-row input { width: auto; margin-bottom: 0; }

  .btn {
    display: inline-block;
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 3px;
    font-family: 'Space Mono', monospace;
    font-size: 0.78rem;
    font-weight: 700;
    cursor: pointer;
    transition: opacity 0.15s, transform 0.1s;
  }
  .btn:hover { opacity: 0.85; transform: translateY(-1px); }
  .btn-primary { background: var(--acc); color: #fff; }
  .btn-secondary { background: var(--acc2); color: #fff; }
  .btn-ghost { background: transparent; border: 1.5px solid var(--border); color: var(--ink); }
  .btn-danger { background: #c0392b; color: #fff; font-size: 0.7rem; padding: 0.3rem 0.6rem; }
  .btn-sm { font-size: 0.68rem; padding: 0.3rem 0.6rem; }

  /* Weight reader widget */
  .weight-widget {
    background: var(--ink);
    color: var(--paper);
    border-radius: 4px;
    padding: 0.8rem;
    margin-bottom: 0.7rem;
  }
  .weight-widget .reading {
    font-size: 1.8rem;
    font-weight: 700;
    font-family: 'Syne', sans-serif;
    color: #7dff9a;
    min-height: 2.2rem;
    letter-spacing: -0.02em;
  }
  .weight-widget small { font-size: 0.65rem; color: var(--muted); }

  /* ── MAIN CONTENT ── */
  main { padding: 1.5rem 2rem; }

  /* flash messages */
  .flash {
    padding: 0.7rem 1rem;
    border-radius: 3px;
    margin-bottom: 1rem;
    font-size: 0.78rem;
    border-left: 4px solid;
  }
  .flash.ok  { background: #eafbea; border-color: #2ecc71; color: #1a7a3a; }
  .flash.err { background: #fbeaea; border-color: var(--acc); color: #8a1a1a; }

  /* search bar */
  .search-bar {
    display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: flex-end;
    margin-bottom: 1.2rem;
    background: var(--card);
    border: 1.5px solid var(--border);
    border-radius: 4px;
    padding: 0.8rem 1rem;
  }
  .search-bar input, .search-bar select {
    margin-bottom: 0;
    width: auto;
    flex: 1 1 120px;
  }

  /* table */
  .table-wrap { overflow-x: auto; }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
  }
  thead tr {
    background: var(--ink);
    color: var(--paper);
  }
  thead th {
    padding: 0.6rem 0.8rem;
    text-align: left;
    font-family: 'Syne', sans-serif;
    font-size: 0.68rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }
  tbody tr { border-bottom: 1px solid var(--border); }
  tbody tr:hover { background: #faf7f0; }
  tbody td { padding: 0.55rem 0.8rem; vertical-align: middle; }

  .chip {
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 30px;
    font-size: 0.65rem;
    font-weight: 700;
  }
  .chip-yes { background: #d4f8e0; color: #1a7a3a; }
  .chip-no  { background: #fde8e8; color: #8a1a1a; }

  .colour-dot {
    display: inline-block;
    width: 10px; height: 10px;
    border-radius: 50%;
    margin-right: 5px;
    border: 1px solid #ccc;
    vertical-align: middle;
  }
  .empty { text-align: center; color: var(--muted); padding: 3rem 0; font-size: 0.85rem; }

  /* update inline form */
  .update-form { display: none; padding: 0.8rem; background: var(--paper); border-top: 1px solid var(--border); }
  .update-form.open { display: block; }
  .update-form .row { display: flex; gap: 0.5rem; flex-wrap: wrap; }
  .update-form .row input, .update-form .row select { margin-bottom: 0; flex: 1 1 100px; }

  @media (max-width: 800px) {
    .page { grid-template-columns: 1fr; }
    aside { border-right: none; border-bottom: 2px solid var(--border); }
  }
</style>
</head>
<body>

<header>
  <span style="font-size:1.4rem">🖨️</span>
  <h1>Stock Manager</h1>
  <span class="badge">EngiConsulting</span>
</header>

<div class="page">

  <!-- ── SIDEBAR ── -->
  <aside>

    <!-- Arduino weight reader -->
    <div>
      <div class="panel-title">⚖️ Arduino Weight Reader</div>
      <div class="weight-widget">
        <div class="reading" id="weight-display">— g</div>
        <small>Live reading from serial port</small>
      </div>
      <button class="btn btn-secondary" style="width:100%" onclick="readWeight()">Read Weight</button>
      <div id="serial-error" style="color:var(--acc);font-size:0.7rem;margin-top:0.4rem"></div>
    </div>

    <!-- Add item form -->
    <div>
      <div class="panel-title">➕ Add New Item</div>
      <form action="/add" method="POST" id="add-form">

        <label>Colour</label>
        <select name="colour" required>
          {% for code, name in colours.items() %}
          <option value="{{ code }}">{{ code }} — {{ name }}</option>
          {% endfor %}
        </select>

        <label>Number (0–9999)</label>
        <input type="number" name="number" min="0" max="9999" required>

        <label>Arrival Date (DD/MM/YYYY)</label>
        <input type="text" name="arrival_date" placeholder="21/01/2026" required>

        <label>Weight (g)</label>
        <div style="display:flex;gap:0.4rem;align-items:center;margin-bottom:0.3rem">
          <input type="number" name="weight_g" id="weight_g_field" step="0.1" min="0" placeholder="0.0" style="margin-bottom:0">
          <button type="button" class="btn btn-ghost btn-sm" onclick="fillWeight()">↑ Use Arduino</button>
        </div>

        <div class="checkbox-row">
          <input type="checkbox" name="in_stock" id="in_stock" checked>
          <label for="in_stock" style="margin:0">In stock</label>
        </div>

        <label>Notes (optional)</label>
        <textarea name="notes" rows="2" placeholder="Any additional info…"></textarea>

        <button type="submit" class="btn btn-primary" style="width:100%">Add to Stock</button>
      </form>
    </div>

    <!-- Search -->
    <div>
      <div class="panel-title">🔍 Filter Stock</div>
      <form action="/search" method="GET">
        <label>Item ID</label>
        <input type="text" name="item_id" placeholder="e.g. R000421012026">

        <label>Colour</label>
        <select name="colour">
          <option value="">All</option>
          {% for code, name in colours.items() %}
          <option value="{{ code }}">{{ name }}</option>
          {% endfor %}
        </select>

        <label>In Stock</label>
        <select name="in_stock">
          <option value="">All</option>
          <option value="y">Yes</option>
          <option value="n">No</option>
        </select>

        <div style="display:flex;gap:0.4rem">
          <div style="flex:1">
            <label>Min weight (g)</label>
            <input type="number" name="min_weight" step="0.1" min="0" placeholder="0">
          </div>
          <div style="flex:1">
            <label>Max weight (g)</label>
            <input type="number" name="max_weight" step="0.1" min="0" placeholder="∞">
          </div>
        </div>
        <button type="submit" class="btn btn-ghost" style="width:100%">Apply Filter</button>
      </form>
    </div>

  </aside>

  <!-- ── MAIN ── -->
  <main>

    {% if msg %}
    <div class="flash ok">✓ {{ msg }}</div>
    {% endif %}
    {% if err %}
    <div class="flash err">✗ {{ err }}</div>
    {% endif %}

    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
      <h2 style="font-family:'Syne',sans-serif;font-weight:800;font-size:1.1rem">
        {% if search_active is defined and search_active %}Filtered Results{% else %}All Stock{% endif %}
        <span style="font-weight:400;color:var(--muted);font-size:0.8rem">({{ items|length }} item{{ 's' if items|length != 1 }})</span>
      </h2>
      {% if search_active is defined and search_active %}
      <a href="/" class="btn btn-ghost btn-sm">← Clear filter</a>
      {% endif %}
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Item ID</th>
            <th>Colour</th>
            <th>In Stock</th>
            <th>Weight (g)</th>
            <th>Arrival</th>
            <th>Notes</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
        {% if items %}
          {% for item in items %}
          <tr>
            <td><code style="font-size:0.72rem">{{ item.item_id }}</code></td>
            <td>
              <span class="colour-dot" style="background:{{ item.colour.lower() }}"></span>
              {{ item.colour }}
            </td>
            <td>
              <span class="chip {{ 'chip-yes' if item.is_in_stock else 'chip-no' }}">
                {{ 'Yes' if item.is_in_stock else 'No' }}
              </span>
            </td>
            <td>{{ item.weight_g }}</td>
            <td>{{ item.arrival_date }}</td>
            <td style="max-width:160px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ item.notes or '—' }}</td>
            <td>
              <button class="btn btn-ghost btn-sm" onclick="toggleUpdate('{{ item.item_id }}')">Edit</button>
              <form action="/delete/{{ item.item_id }}" method="POST" style="display:inline"
                    onsubmit="return confirm('Delete {{ item.item_id }}?')">
                <button type="submit" class="btn btn-danger">Del</button>
              </form>
            </td>
          </tr>
          <!-- inline update row -->
          <tr>
            <td colspan="7" style="padding:0;border:none">
              <div class="update-form" id="upd-{{ item.item_id }}">
                <form action="/update" method="POST">
                  <input type="hidden" name="item_id" value="{{ item.item_id }}">
                  <div class="row">
                    <div>
                      <label>In Stock</label>
                      <select name="is_in_stock">
                        <option value="">— no change —</option>
                        <option value="y">Yes</option>
                        <option value="n">No</option>
                      </select>
                    </div>
                    <div>
                      <label>Weight (g)</label>
                      <input type="number" name="weight_g" step="0.1" placeholder="{{ item.weight_g }}">
                    </div>
                    <div style="flex:2">
                      <label>Notes</label>
                      <input type="text" name="notes" placeholder="{{ item.notes or '' }}">
                    </div>
                    <div style="display:flex;align-items:flex-end">
                      <button type="submit" class="btn btn-primary btn-sm">Save</button>
                    </div>
                  </div>
                </form>
              </div>
            </td>
          </tr>
          {% endfor %}
        {% else %}
          <tr><td colspan="7" class="empty">No items found in stock.</td></tr>
        {% endif %}
        </tbody>
      </table>
    </div>
  </main>
</div>

<script>
  // ── Arduino weight reader ──────────────────────────────────────────────────
  let lastWeight = null;

  async function readWeight() {
    document.getElementById('weight-display').textContent = '…';
    document.getElementById('serial-error').textContent = '';
    try {
      const res = await fetch('/api/read_weight');
      const data = await res.json();
      if (data.ok) {
        lastWeight = data.weight;
        document.getElementById('weight-display').textContent = data.weight + ' g';
      } else {
        document.getElementById('serial-error').textContent = data.error;
        document.getElementById('weight-display').textContent = '— g';
      }
    } catch (e) {
      document.getElementById('serial-error').textContent = 'Network error.';
    }
  }

  function fillWeight() {
    if (lastWeight !== null) {
      document.getElementById('weight_g_field').value = lastWeight;
    } else {
      alert('Press "Read Weight" first to get a reading from the Arduino.');
    }
  }

  // ── Inline edit toggle ─────────────────────────────────────────────────────
  function toggleUpdate(id) {
    const el = document.getElementById('upd-' + id);
    el.classList.toggle('open');
  }
</script>

</body>
</html>
"""

# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    setup_database()
    app.run(debug=True, port=5000)
