from __future__ import annotations

from datetime import datetime
from io import BytesIO

from utils.health_score import LOW_RISK_SCORE_THRESHOLD, MEDIUM_RISK_SCORE_THRESHOLD


def _safe_float(value, default=0.0):
    """Safely convert value to float with fallback default.
    
    Args:
        value: Value to convert (any type)
        default (float, optional): Fallback value for conversion failures (default: 0.0)
    
    Returns:
        float: Converted float value, or default if conversion fails
    
    Example:
        >>> _safe_float("3.14")
        3.14
        >>> _safe_float(None, 0.0)
        0.0
        >>> _safe_float("invalid", 10.0)
        10.0
        >>> _safe_float(42)
        42.0
    
    Note:
        - Handles None, invalid strings, and non-numeric types gracefully
        - Used extensively in PDF generation to avoid ValueError exceptions
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def generate_report_pdf(report_data: dict) -> bytes:
    """Generate professionally formatted PDF health report from report data.
    
    Primary PDF generation function that creates a multi-section medical report
    with styled tables, color-coded metrics, and visual KPI cards using ReportLab.
    
    Args:
        report_data (dict): Complete report dictionary from build_report_for_range():
            - meta: Report metadata (dates, type, generation time, record count)
            - user: Patient profile (username, age, gender, height, weight, BMI)
            - summary_statistics: Metric averages/min/max
            - trend_analysis: Current vs previous period comparison
            - risk_indicators: Risk classification for each metric
            - medication_adherence: Adherence percentage and dose counts
            - alert_summary: Total and critical alert counts
            - ml_classifier_distribution: ML prediction distribution
            - chronic_condition_summary: Diabetes/hypertension flags
    
    Returns:
        bytes: Complete PDF document as byte string ready for download
    
    Raises:
        RuntimeError: If reportlab package not installed
    
    PDF Structure:
        1. Header: PHMS branding, user info, date range, generation timestamp
        2. Patient Profile: Age, gender, height, weight, BMI with color-coded status
        3. Visual Snapshot: 4 KPI cards (adherence, alerts, health score, records)
        4. Risk Mix: Color-coded risk distribution summary
        5. Section 1: Summary Statistics table (avg/min/max for all metrics)
        6. Section 2: Trend Comparison table (current vs previous with % change)
        7. Section 3: Risk Indicators table (average and risk level)
        8. Section 4: Medication Adherence table (scheduled, taken, %)
        9. Section 5: Alerts Summary table (total and critical counts)
        10. Section 6: ML Classifier Distribution (Low/Medium/High risk counts)
        11. Footer: Local device generation timestamp
    
    Design Features:
        - A4 page size with 18mm margins
        - Professional color scheme (blues, grays)
        - Color-coded risk indicators (green/yellow/red)
        - Styled headers and section separators
        - Grid tables with alternating row colors
        - BMI status badges (Underweight/Normal/Overweight/Obese)
        - KPI status badges (Excellent/Good/Monitor/Low)
    
    Example:
        >>> from reports.services.report_service import build_report_for_range
        >>> report_data = build_report_for_range(user_id=1, ...)
        >>> pdf_bytes = generate_report_pdf(report_data)
        >>> with open('health_report.pdf', 'wb') as f:
        ...     f.write(pdf_bytes)
        >>> len(pdf_bytes)
        85643  # PDF file size in bytes
    
    Note:
        - Requires reportlab package: pip install reportlab
        - Uses ReportLab's Platypus for document assembly
        - All colors use hex codes for consistency
        - Generated at local device timestamp in footer
        - Handles missing data gracefully with "N/A" or default values
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Spacer, Paragraph, Table, TableStyle
    except Exception as exc:
        raise RuntimeError(
            "PDF generation dependency missing. Install reportlab to enable PDF export."
        ) from exc

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title="PHMS Health Report",
        rightMargin=18,
        leftMargin=18,
        topMargin=20,
        bottomMargin=18,
    )
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        "ReportHeader",
        parent=styles["Heading1"],
        textColor=colors.HexColor("#1E3A8A"),
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubHeader",
        parent=styles["Normal"],
        textColor=colors.HexColor("#475569"),
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
    )
    section_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#111827"),
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        spaceBefore=6,
        spaceAfter=6,
    )

    story = []

    meta = report_data.get("meta", {})
    user = report_data.get("user", {})

    story.append(Paragraph("PHMS", styles["Heading3"]))
    story.append(Paragraph("Personal Health Monitoring System - Medical Report", header_style))
    story.append(
        Paragraph(
            (
                f"User: {user.get('username', 'N/A')} | "
                f"Report: {meta.get('report_type', 'custom').title()} | "
                f"Date Range: {meta.get('start_date')} to {meta.get('end_date')}"
            ),
            subtitle_style,
        )
    )
    story.append(
        Paragraph(
            f"Generated At: {meta.get('generated_at', datetime.now().isoformat())}",
            subtitle_style,
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("Patient Profile", section_style))
    story.append(_patient_profile_section(user, colors, mm, Table))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Visual Snapshot", section_style))
    story.append(_kpi_snapshot_table(report_data, colors, Paragraph, ParagraphStyle, styles, mm, Table))
    story.append(Spacer(1, 8))
    story.append(_risk_mix_table(report_data, colors, mm, Table))
    story.append(Spacer(1, 10))

    summary = report_data.get("summary_statistics", {})
    summary_rows = [["Metric", "Average", "Minimum", "Maximum"]]
    for metric, stats in summary.items():
        summary_rows.append([
            metric,
            str(stats.get("avg")),
            str(stats.get("min")),
            str(stats.get("max")),
        ])

    story.append(Paragraph("Section 1: Summary Statistics", section_style))
    story.append(_styled_table(Table(summary_rows, colWidths=[45 * mm, 38 * mm, 38 * mm, 38 * mm]), colors))
    story.append(Spacer(1, 12))

    trend = report_data.get("trend_analysis", {})
    trend_rows = [["Metric", "Current Avg", "Previous Avg", "% Change"]]
    for metric, stats in trend.items():
        trend_rows.append([
            metric,
            str(stats.get("current_avg")),
            str(stats.get("previous_avg")),
            str(stats.get("pct_change")),
        ])

    story.append(Paragraph("Section 2: Trend Comparison", section_style))
    story.append(_styled_table(Table(trend_rows, colWidths=[45 * mm, 35 * mm, 35 * mm, 44 * mm]), colors))
    story.append(Spacer(1, 12))

    risk = report_data.get("risk_indicators", {})
    risk_rows = [["Metric", "Average", "Risk Level"]]
    for metric, stats in risk.items():
        risk_rows.append([metric, str(stats.get("avg")), str(stats.get("status"))])

    story.append(Paragraph("Section 3: Risk Indicators", section_style))
    story.append(_styled_table(Table(risk_rows, colWidths=[55 * mm, 50 * mm, 54 * mm]), colors))
    story.append(Spacer(1, 12))

    med = report_data.get("medication_adherence", {})
    med_rows = [
        ["Total Scheduled", str(med.get("total_scheduled_doses", 0))],
        ["Total Taken", str(med.get("total_taken_doses", 0))],
        ["Adherence %", str(med.get("adherence_percentage", 0.0))],
    ]

    story.append(Paragraph("Section 4: Medication Adherence", section_style))
    story.append(_styled_table(Table([["Metric", "Value"], *med_rows], colWidths=[80 * mm, 79 * mm]), colors))
    story.append(Spacer(1, 12))

    alerts = report_data.get("alert_summary", {})
    alert_rows = [
        ["Total Alerts", str(alerts.get("total_alerts", 0))],
        ["Critical Alerts", str(alerts.get("critical_alerts", 0))],
    ]

    story.append(Paragraph("Section 5: Alerts Summary", section_style))
    story.append(_styled_table(Table([["Metric", "Value"], *alert_rows], colWidths=[80 * mm, 79 * mm]), colors))
    story.append(Spacer(1, 12))

    # ML Classifier Distribution
    ml_dist = report_data.get("ml_classifier_distribution", {})
    ml_rows = [
        ["Low Risk Predictions", str(ml_dist.get("Low Risk", 0))],
        ["Medium Risk Predictions", str(ml_dist.get("Medium Risk", 0))],
        ["High Risk Predictions", str(ml_dist.get("High Risk", 0))],
        ["Total Predictions", str(ml_dist.get("total_predictions", 0))],
    ]

    story.append(Paragraph("Section 6: ML Classifier Risk Distribution", section_style))
    story.append(_styled_table(Table([["Category", "Count"], *ml_rows], colWidths=[80 * mm, 79 * mm]), colors))
    story.append(Spacer(1, 16))

    story.append(
        Paragraph(
            f"Generated on: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
            ParagraphStyle(
                "FooterStyle",
                parent=styles["Italic"],
                textColor=colors.HexColor("#64748B"),
                fontSize=8.8,
            ),
        )
    )

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def _patient_profile_section(user, colors_module, mm, Table):
    """Create patient profile table with color-coded BMI status.
    
    Generates a 3-row, 4-column table displaying patient demographics and BMI
    with visual color coding based on WHO BMI categories.
    
    Args:
        user (dict): User data:
            - age (int | None): Patient age in years
            - gender (str | None): Gender (capitalized in output)
            - height (float | None): Height in cm
            - weight (float | None): Weight in kg
            - bmi (float | None): Body Mass Index
        colors_module: ReportLab colors module (colors)
        mm: ReportLab millimeter unit
        Table: ReportLab Table class
    
    Returns:
        Table: Styled ReportLab Table with patient profile data
    
    BMI Color Coding:
        - < 18.5 (Underweight): Red background (#FEE2E2), dark red text
        - 18.5-24.9 (Normal): Green background (#DCFCE7), dark green text
        - 25-29.9 (Overweight): Yellow background (#FFF4D8), dark yellow text
        - >= 30 (Obese): Red background (#FEE2E2), dark red text
        - None: White background, gray text
    
    Layout:
        Row 1: [Age | value | Gender | value]
        Row 2: [Height | value | Weight | value]
        Row 3: [BMI | value (status) | Status | Active]
    
    Example:
        >>> user_data = {
        ...     'age': 35, 'gender': 'male',
        ...     'height': 175, 'weight': 70, 'bmi': 22.9
        ... }
        >>> table = _patient_profile_section(user_data, colors, mm, Table)
        >>> # BMI cell shows "22.9 (Normal)" with green background
    
    Note:
        - Uses gray background for label columns
        - Bold font for labels, regular for values
        - BMI value includes category name in parentheses
        - Missing values displayed as "N/A"
        - Grid borders with light gray color (#CBD5E1)
    """
    from reportlab.platypus import TableStyle

    age = user.get("age") if user.get("age") else "N/A"
    gender = user.get("gender", "N/A").capitalize() if user.get("gender") else "N/A"
    height = f"{user.get('height')} cm" if user.get("height") else "N/A"
    weight = f"{user.get('weight')} kg" if user.get("weight") else "N/A"
    
    bmi = user.get("bmi")
    if bmi:
        bmi_value = f"{round(bmi, 1)}"
        # Determine BMI category and color
        if bmi < 18.5:
            bmi_status = "Underweight"
            bmi_bg = colors_module.HexColor("#FEE2E2")
            bmi_fg = colors_module.HexColor("#991B1B")
        elif bmi < 25:
            bmi_status = "Normal"
            bmi_bg = colors_module.HexColor("#DCFCE7")
            bmi_fg = colors_module.HexColor("#166534")
        elif bmi < 30:
            bmi_status = "Overweight"
            bmi_bg = colors_module.HexColor("#FFF4D8")
            bmi_fg = colors_module.HexColor("#8A5B14")
        else:
            bmi_status = "Obese"
            bmi_bg = colors_module.HexColor("#FEE2E2")
            bmi_fg = colors_module.HexColor("#991B1B")
        bmi_display = f"{bmi_value} ({bmi_status})"
    else:
        bmi_display = "N/A"
        bmi_bg = colors_module.white
        bmi_fg = colors_module.HexColor("#64748B")

    profile_data = [
        ["Age", str(age), "Gender", gender],
        ["Height", height, "Weight", weight],
        ["BMI", bmi_display, "Status", "Active"],
    ]
    
    table = Table(profile_data, colWidths=[32 * mm, 46 * mm, 32 * mm, 46 * mm])
    
    style_commands = [
        ("BACKGROUND", (0, 0), (0, -1), colors_module.HexColor("#F1F5F9")),
        ("BACKGROUND", (2, 0), (2, -1), colors_module.HexColor("#F1F5F9")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors_module.HexColor("#334155")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors_module.HexColor("#334155")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTNAME", (3, 0), (3, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors_module.HexColor("#CBD5E1")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    
    # Add BMI cell background color if BMI exists
    if bmi:
        style_commands.extend([
            ("BACKGROUND", (1, 2), (1, 2), bmi_bg),
            ("TEXTCOLOR", (1, 2), (1, 2), bmi_fg),
            ("FONTNAME", (1, 2), (1, 2), "Helvetica-Bold"),
        ])
    
    table.setStyle(TableStyle(style_commands))
    return table


def _kpi_snapshot_table(report_data, colors_module, Paragraph, ParagraphStyle, styles, mm, Table):
    """Create visual KPI dashboard with 4 color-coded metric cards.
    
    Generates a single-row table containing 4 styled cards displaying key performance
    indicators with dynamic color coding based on thresholds.
    
    Args:
        report_data (dict): Full report data dictionary
        colors_module: ReportLab colors module
        Paragraph: ReportLab Paragraph class
        ParagraphStyle: ReportLab ParagraphStyle class
        styles: ReportLab style sheet
        mm: ReportLab millimeter unit
        Table: ReportLab Table class
    
    Returns:
        Table: Styled wrapper table containing 4 KPI cards
    
    KPI Cards (left to right):
        1. Medication Adherence %:
           - Excellent (>= 85%): Green
           - Needs Attention (65-84%): Yellow
           - Low (< 65%): Red
        
        2. Critical Alerts:
           - Stable (0): Green
           - Monitor (1-2): Yellow
           - High (>= 3): Red
        
          3. Average Health Score:
              - Good (>= 80): Green
              - Moderate (60-79): Yellow
           - Risky (< 60): Red
           - No Data: Yellow
        
        4. Records Count:
           - Available (> 0): Blue
           - No Data (0): Yellow
    
    Card Structure (each):
        - Label: Small gray text at top
        - Value: Large bold number in center
        - Badge: Status text with colored background at bottom
    
    Example:
        >>> kpi_table = _kpi_snapshot_table(report_data, ...)
        >>> # Card 1: "92.5%" with green "Excellent" badge
        >>> # Card 2: "0" with green "Stable" badge
        >>> # Card 3: "85.2" with green "Good" badge
        >>> # Card 4: "50" with blue "Available" badge
    
    Note:
        - All 4 cards have equal width (39mm each)
        - Cards styled with light blue background (#F8FAFF)
        - Light blue borders (#D7E0EE)
        - Values rounded to 2 decimals for percentages
        - Handles None/missing values gracefully
    """
    from reportlab.platypus import TableStyle

    summary = report_data.get("summary_statistics", {})
    med = report_data.get("medication_adherence", {})
    alerts = report_data.get("alert_summary", {})
    meta = report_data.get("meta", {})

    adherence = _safe_float(med.get("adherence_percentage"), 0.0)
    critical_alerts = int(_safe_float(alerts.get("critical_alerts"), 0))
    avg_health_score = summary.get("health_score", {}).get("avg")
    records = int(_safe_float(meta.get("record_count"), 0))

    def adherence_badge(v):
        if v >= 85:
            return "Excellent", colors_module.HexColor("#166534"), colors_module.HexColor("#DCFCE7")
        if v >= 65:
            return "Needs Attention", colors_module.HexColor("#8A5B14"), colors_module.HexColor("#FFF4D8")
        return "Low", colors_module.HexColor("#991B1B"), colors_module.HexColor("#FEE2E2")

    def alert_badge(v):
        if v == 0:
            return "Stable", colors_module.HexColor("#166534"), colors_module.HexColor("#DCFCE7")
        if v <= 2:
            return "Monitor", colors_module.HexColor("#8A5B14"), colors_module.HexColor("#FFF4D8")
        return "High", colors_module.HexColor("#991B1B"), colors_module.HexColor("#FEE2E2")

    def hs_badge(v):
        if v is None:
            return "No Data", colors_module.HexColor("#8A5B14"), colors_module.HexColor("#FFF4D8")
        score = _safe_float(v, 0)
        if score >= LOW_RISK_SCORE_THRESHOLD:
            return "Good", colors_module.HexColor("#166534"), colors_module.HexColor("#DCFCE7")
        if score >= MEDIUM_RISK_SCORE_THRESHOLD:
            return "Moderate", colors_module.HexColor("#8A5B14"), colors_module.HexColor("#FFF4D8")
        return "Risky", colors_module.HexColor("#991B1B"), colors_module.HexColor("#FEE2E2")

    def record_badge(v):
        if v > 0:
            return "Available", colors_module.HexColor("#1E40AF"), colors_module.HexColor("#DBEAFE")
        return "No Data", colors_module.HexColor("#8A5B14"), colors_module.HexColor("#FFF4D8")

    value_style = ParagraphStyle(
        "KpiValueStyle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        textColor=colors_module.HexColor("#1F2A44"),
    )
    label_style = ParagraphStyle(
        "KpiLabelStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        textColor=colors_module.HexColor("#5B6678"),
        leading=10,
    )

    ad_text, ad_fg, ad_bg = adherence_badge(adherence)
    al_text, al_fg, al_bg = alert_badge(critical_alerts)
    hs_text, hs_fg, hs_bg = hs_badge(avg_health_score)
    rc_text, rc_fg, rc_bg = record_badge(records)

    badges = [
        (ad_text, ad_fg, ad_bg),
        (al_text, al_fg, al_bg),
        (hs_text, hs_fg, hs_bg),
        (rc_text, rc_fg, rc_bg),
    ]

    # Each card is a 3-row table: [label], [value], [badge]
    cards = [
        [[Paragraph("Adherence %", label_style)], [Paragraph(f"{round(adherence, 2)}%", value_style)], [ad_text]],
        [[Paragraph("Critical Alerts", label_style)], [Paragraph(str(critical_alerts), value_style)], [al_text]],
        [[Paragraph("Avg Health Score", label_style)], [Paragraph(str(avg_health_score if avg_health_score is not None else "-"), value_style)], [hs_text]],
        [[Paragraph("Records", label_style)], [Paragraph(str(records), value_style)], [rc_text]],
    ]

    row1 = [Table(cards[0], colWidths=[39 * mm]), Table(cards[1], colWidths=[39 * mm]), Table(cards[2], colWidths=[39 * mm]), Table(cards[3], colWidths=[39 * mm])]
    wrapper = Table([row1], colWidths=[39 * mm, 39 * mm, 39 * mm, 39 * mm])

    for idx, cell_table in enumerate(row1):
        cell_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors_module.HexColor("#F8FAFF")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors_module.HexColor("#D7E0EE")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("FONTNAME", (0, 2), (0, 2), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 2), (0, 2), 8),
                    ("TEXTCOLOR", (0, 2), (0, 2), badges[idx][1]),
                    ("BACKGROUND", (0, 2), (0, 2), badges[idx][2]),
                    ("ALIGN", (0, 2), (0, 2), "CENTER"),
                ]
            )
        )

    wrapper.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return wrapper


def _risk_mix_table(report_data, colors_module, mm, Table):
    """Create risk distribution summary table with color-coded cells.
    
    Generates a compact 2-row table showing count of metrics in each risk category
    (normal/warning/critical) with visual color coding.
    
    Args:
        report_data (dict): Full report data dictionary with risk_indicators
        colors_module: ReportLab colors module
        mm: ReportLab millimeter unit
        Table: ReportLab Table class
    
    Returns:
        Table: Styled 2x4 table showing risk distribution
    
    Table Structure:
        Row 1 (Header): [Risk Mix | Normal | Warning | Critical]
        Row 2 (Counts): [Metrics Count | n | w | c]
    
    Color Coding:
        - Normal column: Green background (#DCFCE7), dark green text
        - Warning column: Yellow background (#FFF4D8), dark yellow text
        - Critical column: Red background (#FEE2E2), dark red text
        - Header row: Light blue background (#EEF2FF), dark blue text
    
    Example:
        >>> risk_table = _risk_mix_table(report_data, colors, mm, Table)
        >>> # Output: Risk Mix | Normal: 5 | Warning: 2 | Critical: 1
    
    Note:
        - Counts extracted from risk_indicators section of report_data
        - Only counts metrics with recognized status values
        - Cell alignment: CENTER for all cells
        - Grid borders with light gray color
        - Font size: 8.8pt
    """
    from reportlab.platypus import TableStyle

    risk_data = report_data.get("risk_indicators", {})
    counts = {"normal": 0, "warning": 0, "critical": 0}

    for item in risk_data.values():
        status = str((item or {}).get("status", "")).lower()
        if status in counts:
            counts[status] += 1

    rows = [
        ["Risk Mix", "Normal", "Warning", "Critical"],
        ["Metrics Count", str(counts["normal"]), str(counts["warning"]), str(counts["critical"])],
    ]
    table = Table(rows, colWidths=[45 * mm, 38 * mm, 38 * mm, 38 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors_module.HexColor("#EEF2FF")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors_module.HexColor("#1E3A8A")),
                ("BACKGROUND", (1, 1), (1, 1), colors_module.HexColor("#DCFCE7")),
                ("TEXTCOLOR", (1, 1), (1, 1), colors_module.HexColor("#166534")),
                ("BACKGROUND", (2, 1), (2, 1), colors_module.HexColor("#FFF4D8")),
                ("TEXTCOLOR", (2, 1), (2, 1), colors_module.HexColor("#8A5B14")),
                ("BACKGROUND", (3, 1), (3, 1), colors_module.HexColor("#FEE2E2")),
                ("TEXTCOLOR", (3, 1), (3, 1), colors_module.HexColor("#991B1B")),
                ("BOX", (0, 0), (-1, -1), 0.4, colors_module.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors_module.HexColor("#CBD5E1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _styled_table(table, colors_module):
    """Apply consistent professional styling to data tables.
    
    Adds uniform visual styling to ReportLab tables for consistent appearance
    across all report sections.
    
    Args:
        table (Table): ReportLab Table instance to style
        colors_module: ReportLab colors module
    
    Returns:
        Table: Same table instance with styling applied (modifies in-place)
    
    Applied Styles:
        - Header row (row 0):
            * Light blue background (#DBEAFE)
            * Dark blue text (#1E3A8A)
            * Bold font
        - Data rows (row 1+):
            * Alternating white and light gray backgrounds (#F8FAFC)
            * Regular Helvetica font
        - Grid:
            * Light gray borders (#CBD5E1), 0.35pt thickness
        - Padding: 5pt top and bottom
        - Alignment: LEFT horizontal, MIDDLE vertical
        - Font size: 9pt throughout
    
    Example:
        >>> data = [['Metric', 'Value'], ['heart_rate', '72'], ['sugar', '110']]
        >>> table = Table(data, colWidths=[50*mm, 50*mm])
        >>> styled = _styled_table(table, colors)
        >>> # Table now has blue header and zebra-striped rows
    
    Note:
        - Modifies table in-place but also returns it for chaining
        - Used for all summary statistics and data tables in PDF
        - Header row must be row 0 (first row)
        - Does NOT apply special column formatting (use specialized functions for that)
    """
    from reportlab.platypus import TableStyle

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors_module.HexColor("#DBEAFE")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors_module.HexColor("#1E3A8A")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors_module.HexColor("#CBD5E1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors_module.white, colors_module.HexColor("#F8FAFC")]),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table
