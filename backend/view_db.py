"""
NMVS Database Viewer (CLI & Web Viewer)
Allows viewing, inspecting, and querying all tables in the PostgreSQL database.
Usage:
    python view_db.py                  # View formatted summary and all tables
    python view_db.py --table devices  # View specific table (devices, users, alerts, monitoring, bandwidth)
    python view_db.py --limit 20       # Limit rows displayed
    python view_db.py --json           # Output as JSON
    python view_db.py --serve          # Launch a local browser-based database viewer
"""
import sys
import os
import argparse
import json
from typing import List, Dict, Any

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database.database as database
from app.timezone import as_ist, now_ist

SessionLocal = database.SessionLocal
engine = database.engine
DB_TYPE = database.DB_TYPE
POSTGRES_USER = getattr(database, "POSTGRES_USER", "")
POSTGRES_HOST = getattr(database, "POSTGRES_HOST", "")
POSTGRES_PORT = getattr(database, "POSTGRES_PORT", "")
POSTGRES_DB = getattr(database, "POSTGRES_DB", "SQLite")
from app.users.model import User
from app.devices.model import Device
from app.alerts.model import Alert
from app.monitoring.model import MonitoringHistory
from app.speed_monitoring.model import DeviceBandwidthHistory


def format_table(headers: List[str], rows: List[List[Any]]) -> str:
    """Format headers and rows into a clean, aligned ASCII table."""
    if not rows:
        return "(No records found)"

    str_rows = []
    for row in rows:
        str_rows.append([str(c) if c is not None else "NULL" for c in row])

    col_widths = [len(h) for h in headers]
    for row in str_rows:
        for i, val in enumerate(row):
            # Truncate very long fields
            truncated = val if len(val) <= 45 else val[:42] + "..."
            row[i] = truncated
            col_widths[i] = max(col_widths[i], len(truncated))

    sep = "+" + "+".join(["-" * (w + 2) for w in col_widths]) + "+"
    header_line = "| " + " | ".join([h.ljust(w) for h, w in zip(headers, col_widths)]) + " |"

    lines = [sep, header_line, sep]
    for row in str_rows:
        row_line = "| " + " | ".join([val.ljust(w) for val, w in zip(row, col_widths)]) + " |"
        lines.append(row_line)
    lines.append(sep)

    return "\n".join(lines)


def get_table_data(table_name: str, limit: int = 20) -> Dict[str, Any]:
    """Fetch structured headers and rows for a given table."""
    db = SessionLocal()
    try:
        table_name = table_name.lower().strip()
        if table_name in ("devices", "device"):
            query = db.query(Device).order_by(Device.id.asc()).limit(limit).all()
            headers = ["ID", "Name", "IP Address", "Device Type", "Created At", "Updated At"]
            rows = [
                [
                    d.id,
                    d.name,
                    d.ip,
                    d.device_type,
                    as_ist(d.created_at).strftime("%Y-%m-%d %H:%M:%S IST") if d.created_at else "",
                    as_ist(d.updated_at).strftime("%Y-%m-%d %H:%M:%S IST") if d.updated_at else ""
                ]
                for d in query
            ]
            total = db.query(Device).count()
            return {"title": "DEVICES", "total": total, "headers": headers, "rows": rows}

        elif table_name in ("users", "user"):
            query = db.query(User).order_by(User.id.asc()).limit(limit).all()
            headers = ["ID", "Username", "Email", "Active", "Verified", "Created At"]
            rows = [
                [
                    u.id,
                    u.username,
                    u.email,
                    u.is_active,
                    u.email_verified,
                    as_ist(u.created_at).strftime("%Y-%m-%d %H:%M:%S IST") if u.created_at else ""
                ]
                for u in query
            ]
            total = db.query(User).count()
            return {"title": "USERS", "total": total, "headers": headers, "rows": rows}

        elif table_name in ("alerts", "alert"):
            query = db.query(Alert).order_by(Alert.created_at.desc()).limit(limit).all()
            headers = ["ID", "Device IP", "Title", "Type", "Severity", "Status", "Message", "Created At"]
            rows = [
                [
                    a.id,
                    a.device_ip,
                    a.title or "Alert",
                    a.alert_type,
                    a.severity,
                    a.status,
                    a.message,
                    as_ist(a.created_at).strftime("%Y-%m-%d %H:%M:%S IST") if a.created_at else ""
                ]
                for a in query
            ]
            total = db.query(Alert).count()
            return {"title": "ALERTS", "total": total, "headers": headers, "rows": rows}

        elif table_name in ("monitoring", "monitoring_history"):
            query = db.query(MonitoringHistory).order_by(MonitoringHistory.checked_at.desc()).limit(limit).all()
            headers = ["ID", "IP Address", "Status", "Checked At"]
            rows = [
                [
                    m.id,
                    m.ip,
                    m.status,
                    as_ist(m.checked_at).strftime("%Y-%m-%d %H:%M:%S IST") if m.checked_at else ""
                ]
                for m in query
            ]
            total = db.query(MonitoringHistory).count()
            return {"title": "MONITORING HISTORY", "total": total, "headers": headers, "rows": rows}

        elif table_name in ("bandwidth", "device_bandwidth_history", "speed"):
            query = db.query(DeviceBandwidthHistory).order_by(DeviceBandwidthHistory.tested_at.desc()).limit(limit).all()
            headers = ["ID", "IP Address", "Download (Mbps)", "Upload (Mbps)", "Ping (ms)", "Tested At"]
            rows = [
                [
                    b.id,
                    b.ip,
                    f"{b.download_mbps:.2f}" if b.download_mbps is not None else "N/A",
                    f"{b.upload_mbps:.2f}" if b.upload_mbps is not None else "N/A",
                    f"{b.ping_ms:.2f}" if b.ping_ms is not None else "N/A",
                    as_ist(b.tested_at).strftime("%Y-%m-%d %H:%M:%S IST") if b.tested_at else ""
                ]
                for b in query
            ]
            total = db.query(DeviceBandwidthHistory).count()
            return {"title": "BANDWIDTH SPEED HISTORY", "total": total, "headers": headers, "rows": rows}

        else:
            raise ValueError(f"Unknown table '{table_name}'. Options: devices, users, alerts, monitoring, bandwidth")

    finally:
        db.close()


def print_database_overview(limit: int = 10):
    """Print complete overview of the database and all tables."""
    print("=" * 75)
    print("                 NMVS POSTGRESQL DATABASE VIEWER")
    print("=" * 75)
    print(f"Target Database : {engine.url.database or DB_TYPE}")
    print(f"Database Host   : {engine.url.host or 'local'}")
    print(f"Database User   : {POSTGRES_USER or 'local'}")
    print(f"Connection URL  : {engine.url.render_as_string(hide_password=True)}")
    print(f"Current Time    : {now_ist().strftime('%Y-%m-%d %H:%M:%S IST')}")
    print("=" * 75)

    tables = ["devices", "users", "alerts", "bandwidth", "monitoring"]
    for t_name in tables:
        data = get_table_data(t_name, limit=limit)
        print(f"\n>>> Table: {data['title']} (Showing {len(data['rows'])} of {data['total']} total records)")
        print(format_table(data["headers"], data["rows"]))

    print("\n" + "=" * 75)
    print("Run with `--help` for additional display and filtering options.")
    print("=" * 75)


def output_json():
    """Output all database records in JSON format."""
    db = SessionLocal()
    try:
        out = {
            "metadata": {
                "database": engine.url.database or DB_TYPE,
                "host": engine.url.host,
                "timestamp": now_ist().isoformat()
            },
            "devices": [
                {"id": d.id, "name": d.name, "ip": d.ip, "device_type": d.device_type, "created_at": str(d.created_at), "updated_at": str(d.updated_at)}
                for d in db.query(Device).all()
            ],
            "users": [
                {"id": u.id, "username": u.username, "email": u.email, "is_active": u.is_active, "email_verified": u.email_verified, "created_at": str(u.created_at)}
                for u in db.query(User).all()
            ],
            "alerts": [
                {"id": a.id, "device_ip": a.device_ip, "title": a.title, "type": a.alert_type, "severity": a.severity, "status": a.status, "message": a.message, "created_at": str(a.created_at)}
                for a in db.query(Alert).order_by(Alert.id.desc()).limit(50).all()
            ],
            "bandwidth_history": [
                {"id": b.id, "ip": b.ip, "download_mbps": b.download_mbps, "upload_mbps": b.upload_mbps, "ping_ms": b.ping_ms, "tested_at": str(b.tested_at)}
                for b in db.query(DeviceBandwidthHistory).order_by(DeviceBandwidthHistory.id.desc()).limit(50).all()
            ],
            "recent_monitoring": [
                {"id": m.id, "ip": m.ip, "status": m.status, "checked_at": str(m.checked_at)}
                for m in db.query(MonitoringHistory).order_by(MonitoringHistory.id.desc()).limit(50).all()
            ]
        }
        print(json.dumps(out, indent=2))
    finally:
        db.close()


def launch_web_viewer(port: int = 8088):
    """Launch a lightweight interactive HTTP server to view database tables in the browser."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import webbrowser

    class DBViewerHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            tables = ["devices", "users", "alerts", "bandwidth", "monitoring"]
            sections_html = ""
            for t in tables:
                data = get_table_data(t, limit=100)
                th_html = "".join(f"<th>{h}</th>" for h in data["headers"])
                tr_html = ""
                for row in data["rows"]:
                    tds = "".join(f"<td>{val}</td>" for val in row)
                    tr_html += f"<tr>{tds}</tr>"
                sections_html += f"""
                <section class="card">
                    <h2>{data['title']} <span class="badge">{data['total']} records</span></h2>
                    <div class="table-wrap">
                        <table>
                            <thead><tr>{th_html}</tr></thead>
                            <tbody>{tr_html or '<tr><td colspan="10">No records found</td></tr>'}</tbody>
                        </table>
                    </div>
                </section>
                """

            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>NMVS Database Viewer</title>
    <style>
        :root {{
            --bg: #0f172a;
            --surface: #1e293b;
            --border: #334155;
            --text: #f8fafc;
            --text-dim: #94a3b8;
            --primary: #38bdf8;
            --accent: #6366f1;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            padding: 30px;
        }}
        header {{
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 20px;
        }}
        h1 {{ font-size: 24px; color: var(--primary); }}
        .meta {{ color: var(--text-dim); font-size: 14px; margin-top: 5px; }}
        .btn-refresh {{
            background: var(--accent);
            color: #fff;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: bold;
        }}
        .card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.2);
        }}
        .card h2 {{
            font-size: 18px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 12px;
            color: #e2e8f0;
        }}
        .badge {{
            font-size: 12px;
            background: #334155;
            color: var(--primary);
            padding: 3px 8px;
            border-radius: 999px;
        }}
        .table-wrap {{ overflow-x: auto; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th, td {{
            padding: 10px 14px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            background: #0f172a;
            color: var(--text-dim);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.5px;
        }}
        tr:hover td {{ background: rgba(255,255,255,0.02); }}
    </style>
</head>
<body>
    <header>
        <div>
            <h1>NMVS Database Viewer</h1>
            <div class="meta">PostgreSQL Connected: <strong>{POSTGRES_DB}</strong> ({POSTGRES_USER}@{POSTGRES_HOST}:{POSTGRES_PORT})</div>
        </div>
        <a href="/" class="btn-refresh">Refresh Data</a>
    </header>
    <main>
        {sections_html}
    </main>
</body>
</html>
"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

    server = HTTPServer(("127.0.0.1", port), DBViewerHandler)
    url = f"http://localhost:{port}"
    print(f"\n[+] Local Database Viewer running at: {url}")
    print("    Press Ctrl+C to stop server.\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping database viewer server.")
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="NMVS PostgreSQL Database Viewer")
    parser.add_argument("--table", "-t", type=str, help="Specific table to view: devices, users, alerts, monitoring, bandwidth")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Row limit (default: 10)")
    parser.add_argument("--json", "-j", action="store_true", help="Output database tables as JSON")
    parser.add_argument("--serve", "-s", action="store_true", help="Launch interactive browser viewer")

    args = parser.parse_args()

    if args.serve:
        launch_web_viewer()
    elif args.json:
        output_json()
    elif args.table:
        data = get_table_data(args.table, limit=args.limit)
        print(f"\n>>> Table: {data['title']} (Showing {len(data['rows'])} of {data['total']} total records)")
        print(format_table(data["headers"], data["rows"]))
    else:
        print_database_overview(limit=args.limit)


if __name__ == "__main__":
    main()
