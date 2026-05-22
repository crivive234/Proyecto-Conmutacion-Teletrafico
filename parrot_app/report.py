"""
report.py
Genera un reporte HTML de auditoría a partir de los resultados de nmap.

Uso:
    python3 report.py --xml scan.xml --nse nse.txt --http http.txt
                      --out reporte.html --ts 20240101_120000
"""

import re
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# PARSERS
# ─────────────────────────────────────────────────────────────────────────────

def parse_nmap_xml(xml_path: str) -> list[dict]:
    """
    Extrae hosts, puertos y servicios del XML de nmap.
    Devuelve lista de dicts con la info de cada host escaneado.
    """
    hosts = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception:
        return hosts

    for host in root.findall("host"):
        # Dirección IP
        addr_el = host.find("address[@addrtype='ipv4']")
        ip = addr_el.get("addr", "N/A") if addr_el is not None else "N/A"

        # Hostname (nombre DNS)
        hostname_el = host.find(".//hostname")
        hostname = hostname_el.get("name", ip) if hostname_el is not None else ip

        # Estado del host
        status_el = host.find("status")
        state = status_el.get("state", "unknown") if status_el is not None else "unknown"

        # Puertos
        ports = []
        for port in host.findall(".//port"):
            port_id   = port.get("portid", "?")
            protocol  = port.get("protocol", "?")
            state_el  = port.find("state")
            port_state = state_el.get("state", "?") if state_el is not None else "?"
            svc_el    = port.find("service")
            service   = svc_el.get("name", "unknown")    if svc_el is not None else "unknown"
            product   = svc_el.get("product", "")        if svc_el is not None else ""
            version   = svc_el.get("version", "")        if svc_el is not None else ""

            ports.append({
                "port":     port_id,
                "protocol": protocol,
                "state":    port_state,
                "service":  service,
                "product":  product,
                "version":  version,
            })

        hosts.append({
            "ip":       ip,
            "hostname": hostname,
            "state":    state,
            "ports":    ports,
        })

    return hosts


def parse_http_check(http_path: str) -> list[dict]:
    """
    Parsea el archivo de verificación HTTP generado por audit.sh.
    Devuelve lista de {url, status, ok}.
    """
    results = []
    try:
        text = Path(http_path).read_text()
    except Exception:
        return results

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("["):
            continue
        # Extraer status y URL
        match = re.match(r'\[(.+?)\]\s+(http\S+)', line)
        if match:
            raw_status = match.group(1).strip()
            url        = match.group(2).strip()
            is_ok      = "200" in raw_status
            results.append({"url": url, "status": raw_status, "ok": is_ok})

    return results


def read_nse(nse_path: str) -> str:
    """Lee el archivo NSE como texto plano."""
    try:
        return Path(nse_path).read_text()
    except Exception:
        return "(no disponible)"


# ─────────────────────────────────────────────────────────────────────────────
# GENERADOR DE HTML
# ─────────────────────────────────────────────────────────────────────────────

def render_hosts_table(hosts: list[dict]) -> str:
    if not hosts:
        return "<p class='empty'>Sin resultados de escaneo de puertos.</p>"

    rows = ""
    for h in hosts:
        host_label = f"{h['hostname']} ({h['ip']})"
        state_badge = (
            "<span class='badge ok'>UP</span>"
            if h["state"] == "up" else
            "<span class='badge warn'>DOWN</span>"
        )

        if not h["ports"]:
            rows += f"""
            <tr>
              <td>{host_label}</td>
              <td>{state_badge}</td>
              <td colspan="4" class="muted">Sin puertos abiertos encontrados</td>
            </tr>"""
            continue

        for i, p in enumerate(h["ports"]):
            port_state_badge = (
                "<span class='badge ok'>open</span>"
                if p["state"] == "open" else
                f"<span class='badge muted'>{p['state']}</span>"
            )
            service_info = f"{p['product']} {p['version']}".strip() or p["service"]

            rows += f"""
            <tr>
              {"<td rowspan='" + str(len(h['ports'])) + "'>" + host_label + "</td>" if i == 0 else ""}
              {"<td rowspan='" + str(len(h['ports'])) + "'>" + state_badge + "</td>" if i == 0 else ""}
              <td><strong>{p['port']}</strong>/{p['protocol']}</td>
              <td>{port_state_badge}</td>
              <td>{p['service']}</td>
              <td class="muted">{service_info}</td>
            </tr>"""

    return f"""
    <table>
      <thead>
        <tr>
          <th>Host</th><th>Estado</th>
          <th>Puerto</th><th>Estado puerto</th>
          <th>Servicio</th><th>Versión</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""


def render_http_table(checks: list[dict]) -> str:
    if not checks:
        return "<p class='empty'>Sin verificaciones HTTP.</p>"

    rows = ""
    for c in checks:
        cls = "ok" if c["ok"] else "warn"
        rows += f"""
        <tr>
          <td>{c['url']}</td>
          <td><span class='badge {cls}'>{c['status']}</span></td>
        </tr>"""

    return f"""
    <table>
      <thead><tr><th>Endpoint</th><th>Resultado</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>"""


def generate_html(
    hosts:     list[dict],
    http:      list[dict],
    nse_text:  str,
    timestamp: str,
) -> str:
    now    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    n_up   = sum(1 for h in hosts if h["state"] == "up")
    n_ok   = sum(1 for c in http  if c["ok"])
    n_fail = len(http) - n_ok

    hosts_table = render_hosts_table(hosts)
    http_table  = render_http_table(http)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Reporte de Auditoría — {timestamp}</title>
  <style>
    :root {{
      --bg: #0f1117; --surface: #1a1d27; --border: #2a2d3a;
      --text: #e2e8f0; --muted: #64748b;
      --green: #34d399; --yellow: #fbbf24; --red: #f87171;
      --accent: #4f8ef7;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg); color: var(--text);
      font-family: 'Segoe UI', system-ui, sans-serif;
      font-size: 14px; padding: 32px; line-height: 1.6;
    }}
    h1 {{ font-size: 22px; color: var(--accent); margin-bottom: 4px; }}
    h2 {{ font-size: 15px; font-weight: 700; margin: 28px 0 12px;
          color: var(--text); border-bottom: 1px solid var(--border);
          padding-bottom: 6px; }}
    .meta {{ color: var(--muted); font-size: 12px; margin-bottom: 24px; }}
    .cards {{ display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }}
    .card {{
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 10px; padding: 16px 24px; min-width: 140px;
    }}
    .card .num  {{ font-size: 28px; font-weight: 700; color: var(--accent); }}
    .card .label {{ font-size: 11px; color: var(--muted); text-transform: uppercase;
                    letter-spacing: 0.06em; }}
    table {{
      width: 100%; border-collapse: collapse;
      background: var(--surface); border-radius: 8px; overflow: hidden;
      border: 1px solid var(--border); margin-bottom: 8px;
    }}
    th {{ background: #12151e; padding: 10px 14px; text-align: left;
          font-size: 11px; text-transform: uppercase;
          letter-spacing: 0.07em; color: var(--muted); }}
    td {{ padding: 9px 14px; border-top: 1px solid var(--border);
          vertical-align: top; }}
    .badge {{
      display: inline-block; padding: 2px 9px; border-radius: 20px;
      font-size: 11px; font-weight: 700;
    }}
    .badge.ok   {{ background: rgba(52,211,153,.15); color: var(--green); }}
    .badge.warn {{ background: rgba(251,191,36,.15);  color: var(--yellow); }}
    .badge.muted {{ background: rgba(100,116,139,.15); color: var(--muted); }}
    .muted {{ color: var(--muted); }}
    pre {{
      background: #12151e; border: 1px solid var(--border);
      border-radius: 8px; padding: 16px; overflow-x: auto;
      font-size: 12px; line-height: 1.5; color: var(--text);
      white-space: pre-wrap; word-break: break-word;
    }}
    .empty {{ color: var(--muted); font-style: italic; padding: 8px 0; }}
    footer {{
      margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--border);
      color: var(--muted); font-size: 11px;
    }}
  </style>
</head>
<body>

  <h1>🔍 Reporte de Auditoría Interna</h1>
  <div class="meta">
    Generado: {now} &nbsp;·&nbsp;
    Proyecto: DevOps Logo Detector &nbsp;·&nbsp;
    Herramienta: Parrot OS + nmap
  </div>

  <!-- Tarjetas resumen -->
  <div class="cards">
    <div class="card">
      <div class="num">{n_up}</div>
      <div class="label">Hosts activos</div>
    </div>
    <div class="card">
      <div class="num">{sum(len(h['ports']) for h in hosts)}</div>
      <div class="label">Puertos encontrados</div>
    </div>
    <div class="card">
      <div class="num" style="color:var(--green)">{n_ok}</div>
      <div class="label">Endpoints HTTP OK</div>
    </div>
    <div class="card">
      <div class="num" style="color:var(--yellow)">{n_fail}</div>
      <div class="label">Endpoints con error</div>
    </div>
  </div>

  <!-- Escaneo de puertos -->
  <h2>1 — Escaneo de Puertos</h2>
  {hosts_table}

  <!-- Verificación HTTP -->
  <h2>2 — Verificación de Endpoints HTTP</h2>
  {http_table}

  <!-- Scripts NSE -->
  <h2>3 — Scripts NSE (HTTP headers y métodos)</h2>
  <pre>{nse_text}</pre>

  <footer>
    Auditoría generada por el Contenedor Parrot OS &nbsp;·&nbsp;
    Conmutación y Teletráfico — Proyecto Final
  </footer>

</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generador de reporte HTML de auditoría")
    parser.add_argument("--xml",  required=True, help="Archivo XML de nmap")
    parser.add_argument("--nse",  required=True, help="Archivo de salida NSE")
    parser.add_argument("--http", required=True, help="Archivo de verificación HTTP")
    parser.add_argument("--out",  required=True, help="Archivo HTML de salida")
    parser.add_argument("--ts",   default="",    help="Timestamp del reporte")
    args = parser.parse_args()

    hosts    = parse_nmap_xml(args.xml)
    http     = parse_http_check(args.http)
    nse_text = read_nse(args.nse)

    html = generate_html(hosts, http, nse_text, args.ts)

    Path(args.out).write_text(html, encoding="utf-8")
    print(f"Reporte guardado en: {args.out}")
