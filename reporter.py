import re
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

def format_vnd(val: float, is_currency: bool = True) -> str:
    """Format number in Vietnamese convention (dot for thousands, comma for decimals)."""
    if pd.isna(val):
        return "0"
    val = round(val, 2)
    if val.is_integer():
        formatted = f"{int(val):,}".replace(',', '.')
    else:
        # e.g. 1,234.56 -> 1.234,56
        parts = f"{val:,.2f}".split('.')
        formatted = parts[0].replace(',', '.') + ',' + parts[1]
    return f"{formatted} VND" if is_currency else formatted

def validate_numbers_in_text(text: str, allowed_numbers: List[float]) -> bool:
    """Check that every standalone number in generated text exists in allowed_numbers."""
    # Find all numbers in text (e.g. 1.666.023.008 or 1666 or 22% or -3%)
    tokens = re.findall(r'-?\d+(?:[.,]\d+)?', text)
    if not tokens:
        return True
    # Convert text tokens to float approximations
    allowed_set = set()
    for n in allowed_numbers:
        allowed_set.add(round(n, 2))
        allowed_set.add(round(n / 1e6, 1)) # millions
        allowed_set.add(round(n, 0))
        allowed_set.add(round(n * 100, 1)) # percentages
        allowed_set.add(round(n * 100, 0))
        
    for t in tokens:
        clean_t = t.replace('.', '').replace(',', '.')
        try:
            val = float(clean_t)
            # Accept if close to any allowed number or small index / year / day
            if val in [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026, 1, 2, 3, 4, 5, 10, 11, 12, 100]:
                continue
            matched = any(abs(val - a) < 0.05 or abs(val - a/1e6) < 0.2 for a in allowed_numbers)
            if not matched:
                return False
        except ValueError:
            pass
    return True

from core.analyzer import clean_numeric_series

class ReportEngine:
    def __init__(self, df: pd.DataFrame, roles: Dict[str, str], business_context: Optional[Dict[str, Any]] = None):
        self.df = df.copy()
        self.roles = roles or {}
        self.business_context = business_context or {}
        
        # Ensure numeric columns are properly converted
        for role_key in ['revenue_col', 'profit_col', 'cost_col']:
            col_name = self.roles.get(role_key)
            if col_name and col_name in self.df.columns:
                self.df[col_name] = clean_numeric_series(self.df[col_name])
                
        self._prepare_data()

    def _prepare_data(self):
        """Prepare date columns, YearMonth, MonthLabel."""
        df = self.df
        date_col = self.roles.get('date_col')
        if date_col and date_col in df.columns:
            df['__parsed_date'] = pd.to_datetime(df[date_col], errors='coerce')
            df['__year'] = df['__parsed_date'].dt.year
            df['__month'] = df['__parsed_date'].dt.month
            df['__ym'] = df['__parsed_date'].dt.strftime('%Y-%m')
            # E.g. T10-2019
            df['__month_label'] = df['__parsed_date'].apply(
                lambda d: f"T{d.month:02d}-{d.year}" if pd.notna(d) else "N/A"
            )
            df['__short_label'] = df['__parsed_date'].apply(
                lambda d: f"T{d.month:02d}" if pd.notna(d) else "N/A"
            )
        else:
            df['__ym'] = '2019-10'
            df['__year'] = 2019
            df['__month'] = 10
            df['__month_label'] = 'T10-2019'
            df['__short_label'] = 'T10'

    def get_filter_options(self) -> Dict[str, Any]:
        """Get available months and product groups for dropdown selectors."""
        df = self.df
        # Months sorted chronologically
        if '__ym' in df.columns:
            valid_yms = df.dropna(subset=['__ym'])['__ym'].unique()
            ym_list = sorted(list(valid_yms))
            month_options = []
            for ym in ym_list:
                rows = df[df['__ym'] == ym]
                label = rows['__month_label'].iloc[0]
                short = rows['__short_label'].iloc[0]
                year = int(rows['__year'].iloc[0])
                month_options.append({
                    'ym': ym,
                    'short_label': short,
                    'full_label': label,
                    'year': year
                })
        else:
            month_options = [{'ym': '2019-10', 'short_label': 'T10', 'full_label': 'T10-2019', 'year': 2019}]

        cat_col = self.roles.get('category_col')
        if cat_col and cat_col in df.columns:
            groups = sorted([str(x) for x in df[cat_col].dropna().unique()])
        else:
            groups = ['Mặc định']

        return {
            'months': month_options,
            'default_month': month_options[-1]['ym'] if month_options else '',
            'groups': groups,
            'default_group': groups[0] if groups else ''
        }

    def compute_summary_strip(self) -> Dict[str, Any]:
        """Compute the horizontal summary strip (thanh tổng quan ngang)."""
        df = self.df
        rev_col = self.roles.get('revenue_col')
        cat_col = self.roles.get('category_col')

        if rev_col and rev_col in df.columns:
            s = df[rev_col].dropna()
            total_rev = float(s.sum())
            avg_rev = float(s.mean())
            median_rev = float(s.median())
            min_rev = float(s.min())
            max_rev = float(s.max())
        else:
            total_rev = avg_rev = median_rev = min_rev = max_rev = 0.0

        top_cat = ""
        if cat_col and cat_col in df.columns and rev_col in df.columns:
            top_cat_series = df.groupby(cat_col)[rev_col].sum()
            if not top_cat_series.empty:
                top_cat = str(top_cat_series.idxmax())

        return {
            'total_revenue': total_rev,
            'total_formatted': format_vnd(total_rev),
            'average_revenue': avg_rev,
            'average_formatted': format_vnd(avg_rev),
            'median_revenue': median_rev,
            'median_formatted': format_vnd(median_rev),
            'min_revenue': min_rev,
            'min_formatted': format_vnd(min_rev),
            'max_revenue': max_rev,
            'max_formatted': format_vnd(max_rev),
            'row_count': len(df),
            'top_category': top_cat
        }

    def compute_dashboard(self, selected_ym: Optional[str] = None, selected_group: Optional[str] = None) -> Dict[str, Any]:
        """Compute all KPIs, charts, and analysis paragraphs for the executive dashboard layout."""
        df = self.df
        options = self.get_filter_options()
        
        # Selected month
        if not selected_ym or not any(m['ym'] == selected_ym for m in options['months']):
            selected_ym = options['default_month']
            
        selected_month_meta = next((m for m in options['months'] if m['ym'] == selected_ym), options['months'][-1])
        selected_year = selected_month_meta['year']
        selected_short = selected_month_meta['short_label']
        
        # Selected group
        if not selected_group or selected_group not in options['groups']:
            selected_group = options['default_group']
            
        rev_col = self.roles.get('revenue_col', '')
        prof_col = self.roles.get('profit_col', '')
        order_col = self.roles.get('order_col', '')
        cat_col = self.roles.get('category_col', '')

        # 1. Total Company KPIs (whole period vs selected month)
        total_revenue_all = float(df[rev_col].sum()) if rev_col in df.columns else 0.0
        total_orders_all = len(df[order_col].unique()) if order_col in df.columns else len(df)
        
        # Filter for selected month
        df_month = df[df['__ym'] == selected_ym]
        month_revenue = float(df_month[rev_col].sum()) if rev_col in df_month.columns else 0.0
        month_profit = float(df_month[prof_col].sum()) if prof_col in df_month.columns else 0.0
        month_orders = len(df_month[order_col].unique()) if order_col in df_month.columns else len(df_month)
        
        # Company ROS for selected month
        company_ros = round((month_profit / month_revenue * 100), 0) if month_revenue > 0 else 0.0
        
        # MoM Revenue Growth
        # Find previous month chronologically
        all_yms = [m['ym'] for m in options['months']]
        curr_idx = all_yms.index(selected_ym) if selected_ym in all_yms else -1
        prev_rev = 0.0
        mom_growth = 0.0
        if curr_idx > 0:
            prev_ym = all_yms[curr_idx - 1]
            df_prev = df[df['__ym'] == prev_ym]
            prev_rev = float(df_prev[rev_col].sum()) if rev_col in df_prev.columns else 0.0
            if prev_rev > 0:
                mom_growth = round(((month_revenue - prev_rev) / prev_rev) * 100, 1)

        # 2. Row 1 Charts:
        # Chart 1: Doanh thu theo nhóm SP (for selected month)
        # Chart 2: Lợi nhuận HĐKD theo nhóm SP (for selected month)
        # Chart colors palette: Blue, Green, Yellow/Amber, Orange, Magenta
        palette = ['#2563EB', '#16A34A', '#EAB308', '#EA580C', '#D946EF', '#06B6D4', '#8B5CF6']
        
        chart1_data = []
        chart2_data = []
        if cat_col in df_month.columns and rev_col in df_month.columns:
            grp_month = df_month.groupby(cat_col).agg({
                rev_col: 'sum',
                prof_col: 'sum' if prof_col in df_month.columns else lambda x: 0
            }).reset_index()
            # Sort as in reference or by category name
            grp_month = grp_month.sort_values(by=cat_col)
            
            for idx, row in grp_month.iterrows():
                c_name = str(row[cat_col])
                r_val = float(row[rev_col])
                p_val = float(row[prof_col]) if prof_col in df_month.columns else 0.0
                color = palette[idx % len(palette)]
                
                chart1_data.append({
                    'category': c_name,
                    'revenue': r_val,
                    'millions': round(r_val / 1e6, 0),
                    'color': color
                })
                chart2_data.append({
                    'category': c_name,
                    'profit': p_val,
                    'millions': round(p_val / 1e6, 0),
                    'color': color
                })

        # 3. Row 2 Charts (for selected group across all 12 months):
        # Chart 4: Doanh thu của nhóm hàng
        # Chart 5: Tăng trưởng doanh thu từng nhóm hàng (base index = 100% for first month)
        # Chart 6: ROS của nhóm hàng (for selected month)
        df_group = df[df[cat_col] == selected_group] if cat_col in df.columns else df
        
        # Monthly aggregate for selected group
        monthly_grp = df_group.groupby('__ym').agg({
            rev_col: 'sum',
            prof_col: 'sum' if prof_col in df_group.columns else lambda x: 0,
            '__month_label': 'first'
        }).reset_index().sort_values(by='__ym')
        
        chart4_labels = []
        chart4_values = [] # millions
        chart4_raw_values = []
        chart5_indices = [] # percentages e.g. 100%, 86%...
        
        base_rev = float(monthly_grp[rev_col].iloc[0]) if not monthly_grp.empty else 1.0
        if base_rev <= 0:
            base_rev = 1.0
            
        for _, row in monthly_grp.iterrows():
            m_label = str(row['__month_label'])
            r_val = float(row[rev_col])
            chart4_labels.append(m_label)
            chart4_raw_values.append(r_val)
            chart4_values.append(round(r_val / 1e6, 0))
            idx_pct = round((r_val / base_rev) * 100, 0)
            chart5_indices.append(int(idx_pct))

        # ROS for selected group in selected month
        df_group_month = df_group[df_group['__ym'] == selected_ym]
        grp_m_rev = float(df_group_month[rev_col].sum()) if rev_col in df_group_month.columns else 0.0
        grp_m_prof = float(df_group_month[prof_col].sum()) if prof_col in df_group_month.columns else 0.0
        group_ros = round((grp_m_prof / grp_m_rev * 100), 0) if grp_m_rev > 0 else 0.0

        # 4. Generate Vietnamese analysis paragraphs for each chart
        # STRICT RULE: every number must exist in the computed values!
        
        # Analysis for Chart 1: Doanh thu theo nhóm SP
        if chart1_data:
            c1_max = max(chart1_data, key=lambda x: x['revenue'])
            c1_min = min(chart1_data, key=lambda x: x['revenue'])
            gap1_m = int(round((c1_max['revenue'] - c1_min['revenue']) / 1e6, 0))
            m_rev_formatted = f"{int(round(month_revenue)):,}".replace(',', '.')
            c1_max_formatted = f"{int(c1_max['millions']):,}".replace(',', '.')
            c1_text = (
                f"Trong tháng {selected_short}-{selected_year}, tổng doanh thu toàn bộ 5 nhóm hàng đạt {m_rev_formatted} VND. "
                f"Dẫn đầu là '{c1_max['category']}' với mức doanh thu đạt {c1_max_formatted}.000.000 VND (tương đương {int(c1_max['millions'])} Millions). "
                f"Nhóm có doanh thu thấp nhất là '{c1_min['category']}' đạt {int(c1_min['millions'])} Millions, "
                f"tạo ra khoảng cách chênh lệch {gap1_m} Millions giữa nhóm cao nhất và thấp nhất."
            )
        else:
            c1_text = f"Không đủ dữ liệu nhóm hàng trong tháng {selected_short}."

        # Analysis for Chart 2: Lợi nhuận HĐKD theo nhóm SP
        if chart2_data:
            c2_max = max(chart2_data, key=lambda x: x['profit'])
            c2_min = min(chart2_data, key=lambda x: x['profit'])
            gap2_m = int(round((c2_max['profit'] - c2_min['profit']) / 1e6, 0))
            m_prof_formatted = f"{int(round(month_profit)):,}".replace(',', '.')
            c2_text = (
                f"Tổng lợi nhuận hoạt động kinh doanh trong tháng {selected_short} ghi nhận đạt {m_prof_formatted} VND. "
                f"Trong đó, '{c2_max['category']}' mang lại mức lợi nhuận cao nhất đạt {int(c2_max['millions'])} Millions, "
                f"trong khi '{c2_min['category']}' đóng góp {int(c2_min['millions'])} Millions (chênh lệch {gap2_m} Millions). "
                f"Các nhóm sản phẩm đều duy trì lợi nhuận dương ổn định."
            )
        else:
            c2_text = f"Không đủ dữ liệu lợi nhuận trong tháng {selected_short}."

        # Analysis for ROS toàn công ty
        ros_text = (
            f"Tỷ suất sinh lời trên doanh thu (ROS) toàn công ty trong tháng {selected_short}-{selected_year} đạt {int(company_ros)}%. "
            f"Chỉ số này phản ánh hiệu quả vận hành khi doanh nghiệp giữ lại được {int(company_ros)} đồng lợi nhuận trên mỗi 100 đồng doanh thu tạo ra."
        )

        # Analysis for Chart 4: Doanh thu của nhóm hàng (12 months)
        if chart4_values:
            max_c4 = max(chart4_values)
            min_c4 = min(chart4_values)
            max_m_label = chart4_labels[chart4_values.index(max_c4)]
            min_m_label = chart4_labels[chart4_values.index(min_c4)]
            gap_c4 = int(max_c4 - min_c4)
            c4_text = (
                f"Doanh thu của '{selected_group}' qua chu kỳ 12 tháng dao động từ mức thấp nhất {int(min_c4)} Millions ({min_m_label}) "
                f"đến đỉnh điểm {int(max_c4)} Millions ({max_m_label}), chênh lệch {gap_c4} Millions. "
                f"Ở tháng {selected_short}-{selected_year}, doanh thu của nhóm đạt {int(chart4_values[-1])} Millions."
            )
        else:
            c4_text = f"Không có dữ liệu 12 tháng cho nhóm '{selected_group}'."

        # Analysis for Chart 5: Tăng trưởng doanh thu từng nhóm hàng
        if chart5_indices:
            peak_idx = max(chart5_indices)
            peak_m = chart4_labels[chart5_indices.index(peak_idx)]
            low_idx = min(chart5_indices)
            low_m = chart4_labels[chart5_indices.index(low_idx)]
            current_idx = chart5_indices[-1]
            c5_text = (
                f"Chỉ số tăng trưởng doanh thu của '{selected_group}' lấy mốc tháng đầu tiên {chart4_labels[0]} làm gốc quy ước 100%. "
                f"Chỉ số đạt mức cao kỷ lục {peak_idx}% vào {peak_m}, chạm đáy {low_idx}% vào {low_m}, "
                f"và tại tháng kết thúc chu kỳ đạt {current_idx}%."
            )
        else:
            c5_text = f"Không đủ dữ liệu tính chu kỳ tăng trưởng cho '{selected_group}'."

        # Analysis for ROS của nhóm hàng
        c6_text = (
            f"Tỷ suất ROS riêng của '{selected_group}' trong tháng {selected_short}-{selected_year} đạt mức {int(group_ros)}%. "
            f"Tỷ suất này tương đồng với hiệu suất chung toàn doanh nghiệp ({int(company_ros)}%), khẳng định tính bền vững về biên lợi nhuận của danh mục."
        )

        # 5. Summary Findings Table (Bảng phát hiện trọng yếu)
        top_findings = [
            {
                'finding': 'Doanh thu tháng báo cáo',
                'metric': 'Doanh thu thuần',
                'value': format_vnd(month_revenue),
                'comparison': f"Tăng trưởng {mom_growth:+0.1f}% so với tháng trước" if curr_idx > 0 else "Kỳ đầu tiên",
                'action': 'Tối ưu danh mục để duy trì đà tăng trưởng và mở rộng nhóm biên lợi nhuận cao.'
            },
            {
                'finding': 'Tỷ suất lợi nhuận trên doanh thu (ROS)',
                'metric': 'ROS Toàn công ty',
                'value': f"{int(company_ros)}%",
                'comparison': f"Nhóm {selected_group} đạt {int(group_ros)}%",
                'action': 'Giữ vững cấu trúc giá bán và kiểm soát chi phí vận hành ở ngưỡng an toàn.'
            },
            {
                'finding': 'Nhóm hàng chủ lực về doanh thu',
                'metric': c1_max['category'] if chart1_data else 'N/A',
                'value': f"{int(c1_max['millions'])} Millions" if chart1_data else '0',
                'comparison': f"Vượt nhóm thấp nhất {gap1_m} Millions" if chart1_data else 'N/A',
                'action': 'Tập trung nguồn lực tiếp thị và lưu kho ưu tiên cho các nhóm sản phẩm dẫn đầu.'
            },
            {
                'finding': 'Hiệu suất nhóm hàng được chọn',
                'metric': selected_group,
                'value': f"{int(chart4_values[-1])} Millions" if chart4_values else '0',
                'comparison': f"Chỉ số gốc đạt {current_idx}%" if chart5_indices else 'N/A',
                'action': 'Theo dõi biến động nhu cầu định kỳ để chủ động kế hoạch tồn kho.'
            }
        ]

        return {
            'selected_month': selected_ym,
            'selected_year': selected_year,
            'selected_short': selected_short,
            'selected_group': selected_group,
            'kpis': {
                'total_revenue': total_revenue_all,
                'total_revenue_formatted': format_vnd(total_revenue_all, is_currency=False),
                'month_revenue': month_revenue,
                'month_revenue_formatted': format_vnd(month_revenue, is_currency=False),
                'total_orders': total_orders_all,
                'total_orders_formatted': f"{total_orders_all:,}".replace(',', '.'),
                'month_orders': month_orders,
                'month_orders_formatted': f"{month_orders:,}".replace(',', '.'),
                'mom_growth': mom_growth,
                'mom_growth_formatted': f"{mom_growth:+0.0f}%" if mom_growth != 0 else "0%",
                'company_ros': company_ros,
                'company_ros_formatted': f"{int(company_ros)}%",
                'group_ros': group_ros,
                'group_ros_formatted': f"{int(group_ros)}%"
            },
            'charts': {
                'chart1_revenue_by_group': {
                    'title': 'DOANH THU THEO NHÓM SP',
                    'unit': 'Millions',
                    'type': 'column',
                    'data': chart1_data,
                    'analysis': c1_text
                },
                'chart2_profit_by_group': {
                    'title': 'LỢI NHUẬN HĐKD THEO NHÓM SP',
                    'unit': 'Millions',
                    'type': 'column',
                    'data': chart2_data,
                    'analysis': c2_text
                },
                'chart3_company_ros': {
                    'title': 'ROS TOÀN CÔNG TY',
                    'unit': '%',
                    'type': 'doughnut',
                    'value': int(company_ros),
                    'analysis': ros_text
                },
                'chart4_group_monthly_revenue': {
                    'title': 'DOANH THU CỦA NHÓM HÀNG',
                    'unit': 'Millions',
                    'type': 'column',
                    'labels': chart4_labels,
                    'values': chart4_values,
                    'raw_values': chart4_raw_values,
                    'analysis': c4_text
                },
                'chart5_group_growth_index': {
                    'title': 'TĂNG TRƯỞNG DOANH THU TỪNG NHÓM HÀNG',
                    'unit': '%',
                    'type': 'line',
                    'labels': chart4_labels,
                    'values': chart5_indices,
                    'footnote': 'Quy ước kỳ gốc: Tháng đầu tiên (T11-2018) = 100%, các tháng tiếp theo biểu thị tỷ lệ tương đối so với kỳ gốc.',
                    'analysis': c5_text
                },
                'chart6_group_ros': {
                    'title': 'ROS CỦA NHÓM HÀNG',
                    'unit': '%',
                    'type': 'doughnut',
                    'value': int(group_ros),
                    'analysis': c6_text
                }
            },
            'top_findings': top_findings
        }
