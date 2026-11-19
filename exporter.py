import os
import io
import re
from typing import Dict, Any, List
import pandas as pd
import xlsxwriter
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def export_to_csv(df: pd.DataFrame) -> bytes:
    """Export cleaned dataframe to UTF-8-BOM CSV bytes."""
    return df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')

def export_to_excel(df: pd.DataFrame, dashboard_data: Dict[str, Any], audit_log: List[Dict[str, Any]]) -> bytes:
    """Generate professional Excel workbook with cleaned data, stats, KPIs, and embedded native Excel charts."""
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    
    # Formats
    header_fmt = workbook.add_format({
        'bold': True,
        'bg_color': '#1E3A8A',
        'font_color': '#FFFFFF',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })
    kpi_title_fmt = workbook.add_format({
        'bold': True,
        'font_size': 11,
        'font_color': '#475569',
        'bg_color': '#F1F5F9',
        'border': 1
    })
    kpi_val_fmt = workbook.add_format({
        'bold': True,
        'font_size': 14,
        'font_color': '#0F172A',
        'bg_color': '#FFFFFF',
        'border': 1,
        'align': 'center'
    })
    cell_fmt = workbook.add_format({'border': 1, 'valign': 'vcenter'})
    num_fmt = workbook.add_format({'border': 1, 'num_format': '#,##0', 'align': 'right'})
    pct_fmt = workbook.add_format({'border': 1, 'num_format': '0.0%', 'align': 'right'})
    
    # -------------------------------------------------------------
    # Sheet 1: Dashboard & KPIs with Native Charts
    # -------------------------------------------------------------
    ws_dash = workbook.add_worksheet('Báo cáo & Biểu đồ')
    ws_dash.set_column('A:A', 28)
    ws_dash.set_column('B:E', 18)
    ws_dash.set_column('F:I', 18)
    
    ws_dash.write('A1', 'KHÔNG GIAN PHÂN TÍCH - BÁO CÁO ĐIỀU HÀNH', workbook.add_format({'bold': True, 'font_size': 16, 'font_color': '#1E3A8A'}))
    ws_dash.write('A2', f"Kỳ báo cáo: {dashboard_data.get('selected_short', 'T10')} - Năm {dashboard_data.get('selected_year', 2019)} | Nhóm hàng: {dashboard_data.get('selected_group', '')}", workbook.add_format({'italic': True, 'font_color': '#64748B'}))
    
    # Write KPI Strip
    kpis = dashboard_data.get('kpis', {})
    ws_dash.write('A4', 'CHỈ SỐ KPI', header_fmt)
    ws_dash.write('B4', 'GIÁ TRỊ', header_fmt)
    
    kpi_rows = [
        ('TỔNG DOANH THU TOÀN KỲ (VND)', kpis.get('total_revenue', 0)),
        ('DOANH THU THÁNG HIỆN TẠI (VND)', kpis.get('month_revenue', 0)),
        ('TỔNG SỐ ĐƠN HÀNG TOÀN KỲ', kpis.get('total_orders', 0)),
        ('SỐ ĐƠN HÀNG THÁNG HIỆN TẠI', kpis.get('month_orders', 0)),
        ('TĂNG TRƯỞNG DOANH THU (MoM)', f"{kpis.get('mom_growth', 0)}%"),
        ('ROS TOÀN CÔNG TY', f"{kpis.get('company_ros', 0)}%"),
        (f"ROS NHÓM {dashboard_data.get('selected_group', '')}", f"{kpis.get('group_ros', 0)}%")
    ]
    
    for r_idx, (k_name, k_val) in enumerate(kpi_rows, start=4):
        ws_dash.write(r_idx, 0, k_name, kpi_title_fmt)
        if isinstance(k_val, (int, float)):
            ws_dash.write(r_idx, 1, k_val, num_fmt)
        else:
            ws_dash.write(r_idx, 1, str(k_val), kpi_val_fmt)
            
    # Chart Data Table 1: Doanh thu & Lợi nhuận theo nhóm SP
    c1 = dashboard_data.get('charts', {}).get('chart1_revenue_by_group', {})
    c2 = dashboard_data.get('charts', {}).get('chart2_profit_by_group', {})
    c1_data = c1.get('data', [])
    c2_data = c2.get('data', [])
    
    start_row = 13
    ws_dash.write(start_row, 0, 'Nhóm sản phẩm', header_fmt)
    ws_dash.write(start_row, 1, 'Doanh thu (Triệu)', header_fmt)
    ws_dash.write(start_row, 2, 'Lợi nhuận (Triệu)', header_fmt)
    
    for i, item in enumerate(c1_data):
        curr_row = start_row + 1 + i
        ws_dash.write(curr_row, 0, item.get('category', ''), cell_fmt)
        ws_dash.write(curr_row, 1, item.get('millions', 0), num_fmt)
        p_val = c2_data[i].get('millions', 0) if i < len(c2_data) else 0
        ws_dash.write(curr_row, 2, p_val, num_fmt)
        
    num_items = len(c1_data)
    
    # Add native Excel Column Chart 1: Revenue by Group
    chart_col1 = workbook.add_chart({'type': 'column'})
    chart_col1.add_series({
        'name': 'Doanh thu (Millions)',
        'categories': ['Báo cáo & Biểu đồ', start_row + 1, 0, start_row + num_items, 0],
        'values':     ['Báo cáo & Biểu đồ', start_row + 1, 1, start_row + num_items, 1],
        'data_labels': {'value': True},
        'fill': {'color': '#2563EB'}
    })
    chart_col1.set_title({'name': 'DOANH THU THEO NHÓM SP (Millions)'})
    chart_col1.set_y_axis({'name': 'Millions'})
    chart_col1.set_legend({'none': True})
    ws_dash.insert_chart('D4', chart_col1, {'x_scale': 1.1, 'y_scale': 0.95})
    
    # Add native Excel Column Chart 2: Profit by Group
    chart_col2 = workbook.add_chart({'type': 'column'})
    chart_col2.add_series({
        'name': 'Lợi nhuận (Millions)',
        'categories': ['Báo cáo & Biểu đồ', start_row + 1, 0, start_row + num_items, 0],
        'values':     ['Báo cáo & Biểu đồ', start_row + 1, 2, start_row + num_items, 2],
        'data_labels': {'value': True},
        'fill': {'color': '#16A34A'}
    })
    chart_col2.set_title({'name': 'LỢI NHUẬN HĐKD THEO NHÓM SP (Millions)'})
    chart_col2.set_y_axis({'name': 'Millions'})
    chart_col2.set_legend({'none': True})
    ws_dash.insert_chart('D19', chart_col2, {'x_scale': 1.1, 'y_scale': 0.95})
    
    # Chart Data Table 2: 12-month Trend for Selected Group
    c4 = dashboard_data.get('charts', {}).get('chart4_group_monthly_revenue', {})
    c5 = dashboard_data.get('charts', {}).get('chart5_group_growth_index', {})
    labels_12 = c4.get('labels', [])
    values_12 = c4.get('values', [])
    indices_12 = c5.get('values', [])
    
    start_row_12 = start_row + num_items + 3
    ws_dash.write(start_row_12, 0, 'Kỳ', header_fmt)
    ws_dash.write(start_row_12, 1, 'Doanh thu nhóm (Triệu)', header_fmt)
    ws_dash.write(start_row_12, 2, 'Chỉ số tăng trưởng (%)', header_fmt)
    
    for i, lbl in enumerate(labels_12):
        curr_row = start_row_12 + 1 + i
        ws_dash.write(curr_row, 0, lbl, cell_fmt)
        ws_dash.write(curr_row, 1, values_12[i] if i < len(values_12) else 0, num_fmt)
        ws_dash.write(curr_row, 2, indices_12[i] if i < len(indices_12) else 0, num_fmt)
        
    n_12 = len(labels_12)
    # Add native Excel Column Chart 3: Monthly Revenue
    chart_col3 = workbook.add_chart({'type': 'column'})
    chart_col3.add_series({
        'name': 'Doanh thu (Millions)',
        'categories': ['Báo cáo & Biểu đồ', start_row_12 + 1, 0, start_row_12 + n_12, 0],
        'values':     ['Báo cáo & Biểu đồ', start_row_12 + 1, 1, start_row_12 + n_12, 1],
        'data_labels': {'value': True},
        'fill': {'color': '#EA580C'}
    })
    chart_col3.set_title({'name': f"DOANH THU CỦA {dashboard_data.get('selected_group', '')} (Millions)"})
    chart_col3.set_y_axis({'name': 'Millions'})
    chart_col3.set_legend({'none': True})
    ws_dash.insert_chart('D34', chart_col3, {'x_scale': 1.1, 'y_scale': 0.95})
    
    # -------------------------------------------------------------
    # Sheet 2: Dữ liệu đã làm sạch (Cleaned Data)
    # -------------------------------------------------------------
    ws_data = workbook.add_worksheet('Dữ liệu đã làm sạch')
    for c_idx, col in enumerate(df.columns):
        ws_data.write(0, c_idx, str(col), header_fmt)
        ws_data.set_column(c_idx, c_idx, max(len(str(col)) + 3, 14))
        
    for r_idx, row in df.iterrows():
        for c_idx, col in enumerate(df.columns):
            val = row[col]
            if pd.isna(val):
                ws_data.write(r_idx + 1, c_idx, '', cell_fmt)
            elif isinstance(val, (int, float)):
                ws_data.write(r_idx + 1, c_idx, val, num_fmt)
            else:
                ws_data.write(r_idx + 1, c_idx, str(val), cell_fmt)
                
    # -------------------------------------------------------------
    # Sheet 3: Nhật ký làm sạch dữ liệu (Audit Log)
    # -------------------------------------------------------------
    ws_log = workbook.add_worksheet('Nhật ký làm sạch')
    log_headers = ['STT', 'Thời gian', 'Thao tác', 'Cột áp dụng', 'Chi tiết xử lý', 'Dòng trước', 'Dòng sau']
    for c_idx, h in enumerate(log_headers):
        ws_log.write(0, c_idx, h, header_fmt)
    ws_log.set_column('A:A', 6)
    ws_log.set_column('B:B', 18)
    ws_log.set_column('C:D', 25)
    ws_log.set_column('E:E', 40)
    ws_log.set_column('F:G', 12)
    
    for r_idx, entry in enumerate(audit_log, start=1):
        ws_log.write(r_idx, 0, entry.get('id', r_idx), cell_fmt)
        ws_log.write(r_idx, 1, entry.get('timestamp', ''), cell_fmt)
        ws_log.write(r_idx, 2, entry.get('action_name', ''), cell_fmt)
        ws_log.write(r_idx, 3, entry.get('column', ''), cell_fmt)
        ws_log.write(r_idx, 4, entry.get('details', ''), cell_fmt)
        ws_log.write(r_idx, 5, entry.get('before_rows', 0), cell_fmt)
        ws_log.write(r_idx, 6, entry.get('after_rows', 0), cell_fmt)
        
    workbook.close()
    output.seek(0)
    return output.read()

def export_to_pdf(dashboard_data: Dict[str, Any], summary_strip: Dict[str, Any], business_context: Dict[str, Any]) -> bytes:
    """Generate high-quality PDF report document using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=6
    )
    sub_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=10,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=12
    )
    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=10,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155'),
        spaceAfter=8
    )
    card_title_style = ParagraphStyle(
        'CardTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=colors.HexColor('#64748B'),
        alignment=1
    )
    card_val_style = ParagraphStyle(
        'CardVal',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=1
    )
    
    story = []
    
    # Title
    story.append(Paragraph("KHÔNG GIAN PHÂN TÍCH — BÁO CÁO PHÂN TÍCH DOANH NGHIỆP", title_style))
    meta_info = f"Loại hình doanh nghiệp: {business_context.get('business_type', 'Doanh nghiệp')} | Kỳ báo cáo: {dashboard_data.get('selected_short', 'T10')} - Năm {dashboard_data.get('selected_year', 2019)} | Nhóm hàng: {dashboard_data.get('selected_group', '')}"
    story.append(Paragraph(meta_info, sub_style))
    story.append(Spacer(1, 8))
    
    # 1. Summary Strip Table
    story.append(Paragraph("1. THANH TỔNG SỐ TOÀN DIỆN (SUMMARY STRIP)", h2_style))
    sum_data = [
        [
            Paragraph("TỔNG DOANH THU", card_title_style),
            Paragraph("TRUNG BÌNH", card_title_style),
            Paragraph("TRUNG VỊ", card_title_style),
            Paragraph("NHỎ NHẤT", card_title_style),
            Paragraph("LỚN NHẤT", card_title_style),
            Paragraph("SỐ DÒNG", card_title_style)
        ],
        [
            Paragraph(f"{summary_strip.get('total_formatted', '0')}", card_val_style),
            Paragraph(f"{summary_strip.get('average_formatted', '0')}", card_val_style),
            Paragraph(f"{summary_strip.get('median_formatted', '0')}", card_val_style),
            Paragraph(f"{summary_strip.get('min_formatted', '0')}", card_val_style),
            Paragraph(f"{summary_strip.get('max_formatted', '0')}", card_val_style),
            Paragraph(f"{summary_strip.get('row_count', 0):,}".replace(',', '.'), card_val_style)
        ]
    ]
    t_summary = Table(sum_data, colWidths=[95, 85, 85, 85, 85, 60])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_summary)
    story.append(Spacer(1, 14))
    
    # 2. Executive KPIs (Row 1 Stacked Boxes)
    kpis = dashboard_data.get('kpis', {})
    story.append(Paragraph("2. CHỈ SỐ ĐIỀU HÀNH KỲ HIỆN TẠI (ROW 1 KPIS)", h2_style))
    kpi_grid = [
        [
            Paragraph("TỔNG DOANH THU TOÀN KỲ", card_title_style),
            Paragraph("DOANH THU THÁNG HIỆN TẠI", card_title_style),
            Paragraph("TỔNG ĐƠN HÀNG", card_title_style),
            Paragraph("ĐƠN HÀNG THÁNG HIỆN TẠI", card_title_style),
            Paragraph("TĂNG TRƯỞNG MoM", card_title_style),
            Paragraph("ROS TOÀN CÔNG TY", card_title_style)
        ],
        [
            Paragraph(f"{kpis.get('total_revenue_formatted', '0')} VND", card_val_style),
            Paragraph(f"{kpis.get('month_revenue_formatted', '0')} VND", card_val_style),
            Paragraph(f"{kpis.get('total_orders_formatted', '0')}", card_val_style),
            Paragraph(f"{kpis.get('month_orders_formatted', '0')}", card_val_style),
            Paragraph(f"{kpis.get('mom_growth_formatted', '0%')}", card_val_style),
            Paragraph(f"{kpis.get('company_ros_formatted', '0%')}", card_val_style)
        ]
    ]
    t_kpis = Table(kpi_grid, colWidths=[90, 95, 75, 85, 75, 75])
    t_kpis.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EFF6FF')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#93C5FD')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BFDBFE')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_kpis)
    story.append(Spacer(1, 14))
    
    # 3. Charts and Written Analysis Section
    story.append(Paragraph("3. CHI TIẾT BIỂU ĐỒ & BÌNH LUẬN PHÂN TÍCH CHUYÊN SÂU", h2_style))
    charts = dashboard_data.get('charts', {})
    
    chart_keys = [
        ('chart1_revenue_by_group', 'DOANH THU THEO NHÓM SP (Millions)'),
        ('chart2_profit_by_group', 'LỢI NHUẬN HĐKD THEO NHÓM SP (Millions)'),
        ('chart3_company_ros', 'ROS TOÀN CÔNG TY (%)'),
        ('chart4_group_monthly_revenue', f"DOANH THU CỦA {dashboard_data.get('selected_group', '')} QUA CÁC THÁNG (Millions)"),
        ('chart5_group_growth_index', f"TĂNG TRƯỞNG DOANH THU TỪNG NHÓM HÀNG (KỲ GỐC 100%)"),
        ('chart6_group_ros', f"ROS CỦA {dashboard_data.get('selected_group', '')} (%)")
    ]
    
    for c_key, c_label in chart_keys:
        c_obj = charts.get(c_key, {})
        analysis_p = c_obj.get('analysis', '')
        
        story.append(Paragraph(f"• <b>{c_label}</b>", ParagraphStyle('ChartHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#1E3A8A'))))
        
        # If it's a table-structured chart, render brief table
        if 'data' in c_obj:
            t_rows = [[Paragraph('<b>Nhóm hàng</b>', body_style), Paragraph('<b>Giá trị (Millions)</b>', body_style)]]
            for itm in c_obj['data']:
                t_rows.append([
                    Paragraph(itm.get('category', ''), body_style),
                    Paragraph(f"{itm.get('millions', 0):,.0f} Millions", body_style)
                ])
            t_chart_tbl = Table(t_rows, colWidths=[200, 200])
            t_chart_tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(t_chart_tbl)
            story.append(Spacer(1, 4))
            
        story.append(Paragraph(f"<i>Phân tích:</i> {analysis_p}", body_style))
        story.append(Spacer(1, 8))
        
    # 4. Top Findings Table
    story.append(Spacer(1, 10))
    story.append(Paragraph("4. BẢNG TỔNG HỢP PHÁT HIỆN TRỌNG YẾU (KEY FINDINGS)", h2_style))
    
    top_findings = dashboard_data.get('top_findings', [])
    findings_table_data = [[
        Paragraph('<b>Phát hiện</b>', body_style),
        Paragraph('<b>Chỉ số</b>', body_style),
        Paragraph('<b>Giá trị</b>', body_style),
        Paragraph('<b>So sánh</b>', body_style),
        Paragraph('<b>Hành động khuyến nghị</b>', body_style)
    ]]
    for item in top_findings:
        findings_table_data.append([
            Paragraph(item.get('finding', ''), body_style),
            Paragraph(item.get('metric', ''), body_style),
            Paragraph(item.get('value', ''), body_style),
            Paragraph(item.get('comparison', ''), body_style),
            Paragraph(item.get('action', ''), body_style)
        ])
    t_findings = Table(findings_table_data, colWidths=[100, 90, 80, 110, 140])
    t_findings.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E0E7FF')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#A5B4FC')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#C7D2FE')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_findings)
    
    doc.build(story)
    buffer.seek(0)
    return buffer.read()
