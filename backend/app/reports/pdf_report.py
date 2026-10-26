import io
from collections import Counter

from app.timezone import as_ist, now_ist


class SimplePDFDocument:
    """
    Lightweight, zero-dependency PDF generator adhering to PDF-1.4 specification.
    Draws headers, styled tables, metadata blocks, and footers across pages.
    """

    def __init__(self, title: str, subtitle: str | None = None):
        self.title = title
        self.subtitle = subtitle
        self.pages: list[list[str]] = []
        self.current_page: list[str] = []
        self.width = 595.28   # A4 width in points
        self.height = 841.89  # A4 height in points
        self.margin = 40.0
        self.cursor_y = self.height - self.margin
        self._start_new_page(is_first=True)

    def _start_new_page(self, is_first: bool = False):
        if not is_first:
            self.pages.append(self.current_page)
            self.current_page = []

        self.cursor_y = self.height - self.margin
        self._draw_header()

    def _draw_header(self):
        y = self.cursor_y
        self.current_page.append("0.1 0.2 0.45 rg")  # Deep blue accent
        self.current_page.append(f"{self.margin} {y - 2} {self.width - 2 * self.margin} 2 re f")

        # Document Title
        self.current_page.append("BT")
        self.current_page.append("/F2 16 Tf")
        self.current_page.append("0.05 0.1 0.25 rg")
        self.current_page.append(f"1 0 0 1 {self.margin} {y - 22} Tm")
        self.current_page.append(f"({self._escape_text(self.title)}) Tj")
        self.current_page.append("ET")

        # Subtitle / Timestamp
        timestamp_str = f"Generated: {now_ist().strftime('%Y-%m-%d %H:%M:%S IST')}"
        sub_text = f"{self.subtitle}  |  {timestamp_str}" if self.subtitle else timestamp_str
        self.current_page.append("BT")
        self.current_page.append("/F1 9 Tf")
        self.current_page.append("0.4 0.45 0.5 rg")
        self.current_page.append(f"1 0 0 1 {self.margin} {y - 36} Tm")
        self.current_page.append(f"({self._escape_text(sub_text)}) Tj")
        self.current_page.append("ET")

        self.cursor_y = y - 55

    def add_section_header(self, text: str):
        if self.cursor_y < 120:
            self._start_new_page()

        y = self.cursor_y
        self.current_page.append("BT")
        self.current_page.append("/F2 12 Tf")
        self.current_page.append("0.1 0.2 0.35 rg")
        self.current_page.append(f"1 0 0 1 {self.margin} {y - 14} Tm")
        self.current_page.append(f"({self._escape_text(text)}) Tj")
        self.current_page.append("ET")

        self.current_page.append("0.85 0.88 0.92 rg")
        self.current_page.append(f"{self.margin} {y - 18} {self.width - 2 * self.margin} 1 re f")

        self.cursor_y = y - 28

    def add_table(self, headers: list[str], rows: list[list[str]], col_widths: list[float] | None = None):
        printable_width = self.width - 2 * self.margin
        num_cols = len(headers)

        if not col_widths:
            col_widths = [printable_width / num_cols] * num_cols
        else:
            total_w = sum(col_widths)
            col_widths = [(w / total_w) * printable_width for w in col_widths]

        row_height = 20.0

        if self.cursor_y < row_height * 3:
            self._start_new_page()

        self._draw_table_header(headers, col_widths, row_height)

        for idx, row in enumerate(rows):
            if self.cursor_y < row_height * 2:
                self._start_new_page()
                self._draw_table_header(headers, col_widths, row_height)

            y = self.cursor_y
            if idx % 2 == 1:
                self.current_page.append("0.96 0.97 0.99 rg")
                self.current_page.append(f"{self.margin} {y - row_height} {printable_width} {row_height} re f")

            self.current_page.append("0.9 0.92 0.94 rg")
            self.current_page.append(f"{self.margin} {y - row_height} {printable_width} 0.5 re f")

            curr_x = self.margin + 4
            for c_idx, cell_text in enumerate(row[:num_cols]):
                c_width = col_widths[c_idx]
                trimmed = self._truncate(str(cell_text), int(c_width / 6.5))
                self.current_page.append("BT")
                self.current_page.append("/F1 8.5 Tf")
                self.current_page.append("0.15 0.18 0.22 rg")
                self.current_page.append(f"1 0 0 1 {curr_x} {y - 14} Tm")
                self.current_page.append(f"({self._escape_text(trimmed)}) Tj")
                self.current_page.append("ET")
                curr_x += c_width

            self.cursor_y -= row_height

        self.cursor_y -= 15

    def _draw_text(self, text: str, x: float, y: float, size: float = 8.0, bold: bool = False, color=(0.15, 0.18, 0.22)):
        red, green, blue = color
        self.current_page.extend([
            "BT",
            f"{'/F2' if bold else '/F1'} {size} Tf",
            f"{red:.2f} {green:.2f} {blue:.2f} rg",
            f"1 0 0 1 {x:.1f} {y:.1f} Tm",
            f"({self._escape_text(text)}) Tj",
            "ET",
        ])

    def add_metric_cards(self, metrics: list[tuple[str, str]]):
        if not metrics:
            return
        if self.cursor_y < 100:
            self._start_new_page()

        gap = 8.0
        card_width = (self.width - 2 * self.margin - gap * (len(metrics) - 1)) / len(metrics)
        card_height = 48.0
        for index, (label, value) in enumerate(metrics):
            x = self.margin + index * (card_width + gap)
            y = self.cursor_y
            self.current_page.append("0.95 0.96 0.97 rg")
            self.current_page.append(f"{x:.1f} {y - card_height:.1f} {card_width:.1f} {card_height:.1f} re f")
            self.current_page.append("0.16 0.43 0.58 rg")
            self.current_page.append(f"{x:.1f} {y - card_height:.1f} 3 {card_height:.1f} re f")
            self._draw_text(label, x + 10, y - 17, size=7.5, color=(0.35, 0.39, 0.43))
            self._draw_text(value, x + 10, y - 37, size=13, bold=True, color=(0.08, 0.20, 0.30))

        self.cursor_y -= card_height + 14

    def add_bar_chart(self, title: str, values: list[tuple[str, int]]):
        self.add_section_header(title)
        if not values:
            self._draw_text("No data available", self.margin + 4, self.cursor_y - 10)
            self.cursor_y -= 28
            return

        row_height = 19.0
        if self.cursor_y < len(values) * row_height + 35:
            self._start_new_page()

        printable_width = self.width - 2 * self.margin
        label_width = min(150.0, printable_width * 0.38)
        bar_x = self.margin + label_width
        bar_width = printable_width - label_width - 35
        max_value = max((value for _, value in values), default=0) or 1

        for label, value in values:
            y = self.cursor_y
            self._draw_text(self._truncate(label, 25), self.margin + 3, y - 12, size=7.5)
            self.current_page.append("0.92 0.94 0.96 rg")
            self.current_page.append(f"{bar_x:.1f} {y - 15:.1f} {bar_width:.1f} 9 re f")
            fill_width = max(1.0, bar_width * max(value, 0) / max_value)
            self.current_page.append("0.16 0.43 0.58 rg")
            self.current_page.append(f"{bar_x:.1f} {y - 15:.1f} {fill_width:.1f} 9 re f")
            self._draw_text(str(value), bar_x + bar_width + 5, y - 12, size=7.5, bold=True)
            self.cursor_y -= row_height

        self.cursor_y -= 8

    def add_topology_diagram(self, topology):
        self.add_section_header("Network Topology")
        nodes = list(getattr(topology, "nodes", []) or [])
        edges = list(getattr(topology, "edges", []) or [])
        if not nodes:
            self._draw_text("No devices are available for the topology diagram.", self.margin + 4, self.cursor_y - 10)
            self.cursor_y -= 28
            return

        diagram_height = 250.0
        if self.cursor_y < diagram_height + 45:
            self._start_new_page()

        left = self.margin + 20
        right = self.width - self.margin - 25
        top = self.cursor_y - 12
        bottom = top - diagram_height
        min_x = min(node.x for node in nodes)
        max_x = max(node.x for node in nodes)
        min_y = min(node.y for node in nodes)
        max_y = max(node.y for node in nodes)
        x_span = max(max_x - min_x, 1.0)
        y_span = max(max_y - min_y, 1.0)
        positions = {
            node.id: (
                left + (node.x - min_x) / x_span * (right - left),
                bottom + (max_y - node.y) / y_span * diagram_height,
            )
            for node in nodes
        }

        for edge in edges:
            if edge.source not in positions or edge.target not in positions:
                continue
            x1, y1 = positions[edge.source]
            x2, y2 = positions[edge.target]
            color = "0.15 0.55 0.38" if edge.status == "active" else "0.65 0.32 0.28"
            self.current_page.extend([
                f"{color} RG",
                "0.8 w",
                f"{x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S",
            ])

        font_size = 6.5 if len(nodes) > 18 else 7.5
        label_width = 110 if len(nodes) > 18 else 135
        for node in nodes:
            x, y = positions[node.id]
            if node.status == "Online":
                fill = "0.15 0.55 0.38"
            elif node.status == "Offline":
                fill = "0.72 0.28 0.25"
            else:
                fill = "0.42 0.48 0.55"
            self.current_page.append(f"{fill} rg")
            self.current_page.append(f"{x - 3:.1f} {y - 3:.1f} 6 6 re f")
            label = node.name if node.ip == "0.0.0.0" else f"{node.name} ({node.ip})"
            label_x = min(x + 6, self.width - self.margin - label_width)
            self._draw_text(self._truncate(label, label_width // 4), label_x, y + 2, size=font_size)

        legend_y = bottom - 17
        self.current_page.append("0.15 0.55 0.38 rg")
        self.current_page.append(f"{left:.1f} {legend_y - 2:.1f} 6 6 re f")
        self._draw_text("Online", left + 9, legend_y, size=7)
        self.current_page.append("0.72 0.28 0.25 rg")
        self.current_page.append(f"{left + 65:.1f} {legend_y - 2:.1f} 6 6 re f")
        self._draw_text("Offline", left + 74, legend_y, size=7)
        self.cursor_y = legend_y - 18

    def _draw_table_header(self, headers: list[str], col_widths: list[float], row_height: float):
        y = self.cursor_y
        printable_width = self.width - 2 * self.margin

        self.current_page.append("0.2 0.3 0.5 rg")
        self.current_page.append(f"{self.margin} {y - row_height} {printable_width} {row_height} re f")

        curr_x = self.margin + 4
        for c_idx, h_text in enumerate(headers):
            c_width = col_widths[c_idx]
            trimmed = self._truncate(str(h_text), int(c_width / 7.0))
            self.current_page.append("BT")
            self.current_page.append("/F2 9 Tf")
            self.current_page.append("1.0 1.0 1.0 rg")
            self.current_page.append(f"1 0 0 1 {curr_x} {y - 14} Tm")
            self.current_page.append(f"({self._escape_text(trimmed)}) Tj")
            self.current_page.append("ET")
            curr_x += c_width

        self.cursor_y -= row_height

    def _draw_footer(self, page_num: int, total_pages: int, stream: list[str]):
        y = 25.0
        stream.append("0.8 0.85 0.9 rg")
        stream.append(f"{self.margin} {y + 12} {self.width - 2 * self.margin} 0.5 re f")

        stream.append("BT")
        stream.append("/F1 8 Tf")
        stream.append("0.5 0.55 0.6 rg")
        stream.append(f"1 0 0 1 {self.margin} {y} Tm")
        stream.append("(Network Monitoring and Visualization System (NMVS)) Tj")
        stream.append("ET")

        page_str = f"Page {page_num} of {total_pages}"
        stream.append("BT")
        stream.append("/F1 8 Tf")
        stream.append("0.5 0.55 0.6 rg")
        stream.append(f"1 0 0 1 {self.width - self.margin - 55} {y} Tm")
        stream.append(f"({page_str}) Tj")
        stream.append("ET")

    def build(self) -> bytes:
        if self.current_page:
            self.pages.append(self.current_page)

        total_pages = len(self.pages)
        for i, page in enumerate(self.pages):
            self._draw_footer(i + 1, total_pages, page)

        buf = io.BytesIO()
        offsets = []

        def _write(s: str):
            buf.write(s.encode("latin-1"))

        _write("%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

        offsets.append(buf.tell())
        _write("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

        page_refs = [f"{4 + i * 2} 0 R" for i in range(total_pages)]
        offsets.append(buf.tell())
        _write(f"2 0 obj\n<< /Type /Pages /Kids [{ ' '.join(page_refs) }] /Count {total_pages} >>\nendobj\n")

        offsets.append(buf.tell())
        _write("3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\nendobj\n")

        offsets.append(buf.tell())
        font_bold_obj_num = 4 + total_pages * 2
        _write(f"{font_bold_obj_num} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>\nendobj\n")

        for i, page_cmds in enumerate(self.pages):
            page_obj_id = 4 + i * 2
            stream_obj_id = page_obj_id + 1

            offsets.append(buf.tell())
            _write(
                f"{page_obj_id} 0 obj\n"
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.width:.2f} {self.height:.2f}] "
                f"/Contents {stream_obj_id} 0 R "
                f"/Resources << /Font << /F1 3 0 R /F2 {font_bold_obj_num} 0 R >> >> >>\n"
                f"endobj\n"
            )

            content_str = "\n".join(page_cmds) + "\n"
            content_bytes = content_str.encode("latin-1", errors="replace")

            offsets.append(buf.tell())
            _write(
                f"{stream_obj_id} 0 obj\n"
                f"<< /Length {len(content_bytes)} >>\n"
                f"stream\n"
            )
            buf.write(content_bytes)
            _write("endstream\nendobj\n")

        xref_offset = buf.tell()
        total_objs = font_bold_obj_num + 1

        all_offsets = {
            1: offsets[0],
            2: offsets[1],
            3: offsets[2],
            font_bold_obj_num: offsets[3]
        }
        for i in range(total_pages):
            all_offsets[4 + i * 2] = offsets[4 + i * 2]
            all_offsets[5 + i * 2] = offsets[5 + i * 2]

        _write(f"xref\n0 {total_objs}\n")
        _write("0000000000 65535 f \n")
        for obj_id in range(1, total_objs):
            off = all_offsets.get(obj_id, 0)
            _write(f"{off:010d} 00000 n \n")

        _write(
            f"trailer\n"
            f"<< /Size {total_objs} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        )

        return buf.getvalue()

    @staticmethod
    def _escape_text(text: str) -> str:
        text = str(text or "")
        return (
            text.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
            .encode("latin-1", errors="replace")
            .decode("latin-1")
        )

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        s = str(text or "").strip()
        if len(s) > max_chars:
            return s[:max_chars - 2] + ".."
        return s


def generate_executive_summary_pdf(
    devices: list,
    alerts: list,
    bandwidth_records: list,
    health_score: float,
    monitoring_records: list | None = None,
    latest_status: dict[str, str] | None = None,
    topology=None,
    total_alert_count: int | None = None,
    total_speed_test_count: int | None = None,
) -> bytes:
    monitoring_records = monitoring_records or []
    latest_status = latest_status or {}
    status_counts = Counter(latest_status.get(device.ip, "Unknown") for device in devices)
    device_types = Counter(device.device_type or "Unknown" for device in devices)
    device_sources = Counter(getattr(device, "source", "manual") or "manual" for device in devices)
    active_alerts = sum(1 for alert in alerts if alert.status == "active")

    doc = SimplePDFDocument(
        title="NMVS - Executive Network Health Report",
        subtitle=f"Overall Network Health: {health_score:.1f}%"
    )

    total_nodes = getattr(getattr(topology, "summary", None), "total_nodes", len(devices))
    total_edges = getattr(getattr(topology, "summary", None), "total_edges", 0)
    active_edge_count = getattr(getattr(topology, "summary", None), "active_edges", 0)
    subnet_count = len(getattr(topology, "subnets", []) or [])
    doc.add_metric_cards([
        ("Network Health", f"{health_score:.1f}%"),
        ("Devices", str(len(devices))),
        ("Online", str(status_counts.get("Online", 0))),
        ("Active Alerts", str(active_alerts)),
    ])

    doc.add_bar_chart("Device Connectivity", [
        ("Online", status_counts.get("Online", 0)),
        ("Offline", status_counts.get("Offline", 0)),
        ("Unknown", status_counts.get("Unknown", 0)),
    ])
    doc.add_bar_chart("Device Types", sorted(device_types.items(), key=lambda item: (-item[1], item[0])))
    doc.add_bar_chart("Device Origin", sorted(device_sources.items()))
    doc.add_bar_chart("Alert Severity (recent sample)", sorted(Counter(a.severity for a in alerts).items()))

    doc.add_section_header("Network Overview")
    overview_rows = [
        ["Topology devices", str(total_nodes), "Topology links", str(total_edges)],
        ["Active links", str(active_edge_count), "Subnets", str(subnet_count)],
        ["Alerts represented", str(len(alerts)), "Total alerts", str(total_alert_count if total_alert_count is not None else len(alerts))],
        ["Speed tests represented", str(len(bandwidth_records)), "Total speed tests", str(total_speed_test_count if total_speed_test_count is not None else len(bandwidth_records))],
    ]
    doc.add_table(["Metric", "Value", "Metric", "Value"], overview_rows)

    doc.add_topology_diagram(topology)

    subnets = getattr(topology, "subnets", []) or []
    doc.add_section_header("Subnet Inventory")
    doc.add_table(
        ["Subnet", "Gateway", "Devices", "Online", "Hosts"],
        [[s.subnet, s.gateway_ip or "N/A", str(s.device_count), str(s.online_count), str(s.total_hosts)] for s in subnets],
    )

    doc.add_section_header("Complete Device Inventory")
    doc.add_table(
        ["ID", "Name", "IP Address", "Device Type", "Status"],
        [[str(d.id), d.name, d.ip, d.device_type, latest_status.get(d.ip, "Unknown")] for d in devices],
        [35, 140, 115, 105, 70],
    )
    doc.add_table(
        ["ID", "Network Type", "Source", "Registered At (IST)", "Updated At (IST)"],
        [[
            str(d.id),
            getattr(d, "network_type", "Unknown") or "Unknown",
            getattr(d, "source", "manual") or "manual",
            as_ist(d.created_at).strftime("%Y-%m-%d %H:%M:%S") if d.created_at else "N/A",
            as_ist(d.updated_at).strftime("%Y-%m-%d %H:%M:%S") if d.updated_at else "N/A",
        ] for d in devices],
        [35, 150, 65, 125, 125],
    )

    doc.add_section_header(f"Recent Network Alerts (latest {len(alerts)})")
    alert_rows = []
    for alert in alerts:
        created_at = as_ist(alert.created_at).strftime("%Y-%m-%d %H:%M IST") if alert.created_at else "N/A"
        alert_rows.append([
            str(alert.id),
            alert.device_ip,
            alert.title or alert.alert_type,
            alert.severity.upper(),
            alert.status.upper(),
            created_at,
        ])
    doc.add_table(["ID", "IP", "Alert", "Severity", "Status", "Created"], alert_rows)
    if alerts:
        doc.add_table(
            ["Alert ID", "Message"],
            [[str(alert.id), alert.message] for alert in alerts],
            [45, 470],
        )

    doc.add_section_header(f"Recent Monitoring Samples (latest {len(monitoring_records)})")
    doc.add_table(
        ["ID", "IP Address", "Status", "Checked At (IST)"],
        [[
            str(record.id),
            record.ip,
            record.status,
            as_ist(record.checked_at).strftime("%Y-%m-%d %H:%M:%S") if record.checked_at else "N/A",
        ] for record in monitoring_records],
    )

    doc.add_section_header(f"Recent Speed Tests (latest {len(bandwidth_records)})")
    bw_rows = []
    for record in bandwidth_records:
        bw_rows.append([
            str(record.id),
            record.ip,
            f"{record.download_mbps:.1f}" if record.download_mbps is not None else "N/A",
            f"{record.upload_mbps:.1f}" if record.upload_mbps is not None else "N/A",
            f"{record.ping_ms:.1f}" if record.ping_ms is not None else "N/A",
            as_ist(record.tested_at).strftime("%Y-%m-%d %H:%M IST") if record.tested_at else "N/A",
        ])
    doc.add_table(["ID", "Target", "Download", "Upload", "Ping", "Tested At"], bw_rows)

    return doc.build()
