import re
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

def vi_format_num(val: float) -> str:
    """Format integer/float with dot as thousands separator for Vietnamese convention."""
    return f"{int(round(val)):,}".replace(',', '.')

def clean_numeric_series(series: pd.Series) -> pd.Series:
    """Safely convert series to numeric without corrupting decimals."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors='coerce')
        
    def parse_num(v):
        if pd.isna(v):
            return np.nan
        s = str(v).strip()
        if not s or s.lower() in ['nan', 'null', 'none', 'n/a']:
            return np.nan
        # Remove currency symbols and whitespace
        s = re.sub(r'[\sđ₫$€£]', '', s)
        is_pct = '%' in s
        s = s.replace('%', '')
        # Check if formatted like 1.234.567 or 1.234.567,89 (Vietnamese dot thousand separator)
        if re.match(r'^-?\d{1,3}(\.\d{3})+(,\d+)?$', s):
            s = s.replace('.', '').replace(',', '.')
        elif re.match(r'^-?\d{1,3}(,\d{3})+(\.\d+)?$', s):
            s = s.replace(',', '')
        try:
            val = float(s)
            return val / 100.0 if is_pct else val
        except ValueError:
            return np.nan
            
    return series.apply(parse_num)

class DataAnalyzer:
    def __init__(self, df: pd.DataFrame, roles: Dict[str, str], business_context: Optional[Dict[str, Any]] = None):
        self.df = df.copy()
        self.roles = roles or {}
        self.business_context = business_context or {}
        
        # Ensure numeric columns are properly converted to numeric types
        for role_key in ['revenue_col', 'profit_col', 'cost_col']:
            col_name = self.roles.get(role_key)
            if col_name and col_name in self.df.columns:
                self.df[col_name] = clean_numeric_series(self.df[col_name])
        
    def compute_summary_stats(self) -> Dict[str, Any]:
        """Compute comprehensive statistics for numeric, categorical, and date columns."""
        df = self.df
        numeric_stats = {}
        categorical_stats = {}
        date_stats = {}
        
        # 1. Numeric columns
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        for col in num_cols:
            s = df[col].dropna()
            if s.empty:
                continue
            numeric_stats[col] = {
                'count': int(s.count()),
                'sum': float(s.sum()),
                'mean': float(s.mean()),
                'median': float(s.median()),
                'min': float(s.min()),
                'max': float(s.max()),
                'std': float(s.std()) if len(s) > 1 else 0.0
            }
            
        # 2. Categorical columns
        cat_cols = [c for c in df.columns if c not in num_cols]
        for col in cat_cols:
            s = df[col].dropna().astype(str)
            if s.empty:
                continue
            val_counts = s.value_counts()
            top_vals = []
            for val, cnt in val_counts.head(10).items():
                top_vals.append({
                    'value': str(val),
                    'count': int(cnt),
                    'percentage': round((cnt / len(s)) * 100, 2)
                })
            categorical_stats[col] = {
                'distinct_count': int(s.nunique()),
                'top_value': str(val_counts.index[0]) if not val_counts.empty else '',
                'top_count': int(val_counts.iloc[0]) if not val_counts.empty else 0,
                'distribution': top_vals
            }
            
        # 3. Date stats if date column exists
        date_col = self.roles.get('date_col')
        if date_col and date_col in df.columns:
            try:
                date_series = pd.to_datetime(df[date_col], errors='coerce').dropna()
                if not date_series.empty:
                    min_date = date_series.min()
                    max_date = date_series.max()
                    date_stats = {
                        'column': date_col,
                        'min_date': min_date.strftime('%Y-%m-%d'),
                        'max_date': max_date.strftime('%Y-%m-%d'),
                        'total_days': (max_date - min_date).days + 1,
                        'total_months': (max_date.year - min_date.year) * 12 + max_date.month - min_date.month + 1
                    }
            except Exception:
                pass
                
        return {
            'numeric_columns': numeric_stats,
            'categorical_columns': categorical_stats,
            'date_stats': date_stats
        }

    def compute_correlations(self) -> Dict[str, Any]:
        """Compute correlation matrix for numeric columns."""
        df = self.df
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if len(num_cols) < 2:
            return {'columns': num_cols, 'matrix': []}
            
        corr_df = df[num_cols].corr().fillna(0).round(4)
        matrix = []
        for col in num_cols:
            row_vals = [float(corr_df.loc[col, c]) for c in num_cols]
            matrix.append(row_vals)
            
        return {
            'columns': num_cols,
            'matrix': matrix
        }

    def compute_anomalies(self) -> List[Dict[str, Any]]:
        """Identify outliers using 3 standard deviations and IQR method."""
        df = self.df
        anomalies = []
        rev_col = self.roles.get('revenue_col')
        target_cols = [rev_col] if rev_col and rev_col in df.columns else [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])][:2]
        
        for col in target_cols:
            s = df[col].dropna()
            if len(s) < 10:
                continue
            mean = s.mean()
            std = s.std()
            q1 = s.quantile(0.25)
            q3 = s.quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)]
            for idx, row in outliers.head(5).iterrows():
                val = float(row[col])
                z_score = round((val - mean) / std, 2) if std > 0 else 0
                anomalies.append({
                    'row_index': int(idx) + 1,
                    'column': col,
                    'value': val,
                    'mean': round(float(mean), 2),
                    'z_score': z_score,
                    'type': 'Cao bất thường' if val > mean else 'Thấp bất thường',
                    'order_id': str(row.get(self.roles.get('order_col', ''), f'Row #{idx+1}'))
                })
        return anomalies

    def answer_business_questions(self, questions: List[str]) -> List[Dict[str, Any]]:
        """Map user business questions from Step 1 to exact calculations with concrete numbers."""
        df = self.df
        rev_col = self.roles.get('revenue_col', '')
        prof_col = self.roles.get('profit_col', '')
        cat_col = self.roles.get('category_col', '')
        chan_col = self.roles.get('channel_col', '')
        date_col = self.roles.get('date_col', '')
        
        answers = []
        for q in questions:
            q_clean = q.strip()
            if not q_clean:
                continue
            q_lower = q_clean.lower()
            
            answer_text = ""
            metrics_used = {}
            
            # 1. Questions regarding channel (kênh bán hàng)
            if any(k in q_lower for k in ['kênh', 'kenh', 'channel']) and chan_col and rev_col and chan_col in df.columns and rev_col in df.columns:
                grp = df.groupby(chan_col)[rev_col].sum().sort_values(ascending=False)
                if not grp.empty:
                    top_chan = grp.index[0]
                    top_val = float(grp.iloc[0])
                    lowest_chan = grp.index[-1]
                    lowest_val = float(grp.iloc[-1])
                    total_rev = float(df[rev_col].sum())
                    top_pct = round((top_val / total_rev) * 100, 1) if total_rev > 0 else 0
                    
                    answer_text = (
                        f"Kênh bán hàng có doanh thu cao nhất là '{top_chan}' đạt {vi_format_num(top_val)} VND, "
                        f"chiếm {top_pct}% tổng doanh thu toàn bộ ({vi_format_num(total_rev)} VND). "
                        f"Kênh thấp nhất là '{lowest_chan}' với {vi_format_num(lowest_val)} VND."
                    )
                    metrics_used = {'top_channel': top_chan, 'top_revenue': top_val, 'percentage': top_pct}
                
            # 2. Questions regarding product group / category (nhóm hàng, sản phẩm, ngành hàng)
            elif any(k in q_lower for k in ['nhóm', 'sản phẩm', 'ngành hàng', 'mặt hàng', 'category']) and cat_col and rev_col and cat_col in df.columns and rev_col in df.columns:
                grp = df.groupby(cat_col)[rev_col].sum().sort_values(ascending=False)
                if not grp.empty:
                    top_cat = grp.index[0]
                    top_val = float(grp.iloc[0])
                    bot_cat = grp.index[-1]
                    bot_val = float(grp.iloc[-1])
                    gap = top_val - bot_val
                    
                    answer_text = (
                        f"Nhóm hàng dẫn đầu về doanh thu là '{top_cat}' với tổng mức {vi_format_num(top_val)} VND. "
                        f"Nhóm đứng cuối là '{bot_cat}' đạt {vi_format_num(bot_val)} VND, "
                        f"chênh lệch giữa nhóm cao nhất và thấp nhất là {vi_format_num(gap)} VND."
                    )
                    metrics_used = {'top_category': top_cat, 'top_revenue': top_val, 'gap': gap}
                
            # 3. Questions regarding profit or ROS (lợi nhuận, tỷ suất, biên lợi nhuận, ros)
            elif any(k in q_lower for k in ['lợi nhuận', 'loi_nhuan', 'ros', 'tỷ suất', 'hiệu quả']) and rev_col and prof_col and rev_col in df.columns and prof_col in df.columns:
                total_rev = float(df[rev_col].sum())
                total_prof = float(df[prof_col].sum())
                ros = round((total_prof / total_rev) * 100, 1) if total_rev > 0 else 0
                
                if cat_col and cat_col in df.columns:
                    grp_p = df.groupby(cat_col).agg({rev_col: 'sum', prof_col: 'sum'})
                    if not grp_p.empty and grp_p[rev_col].sum() > 0:
                        grp_p['ros'] = (grp_p[prof_col] / grp_p[rev_col] * 100).round(1)
                        best_ros_cat = grp_p['ros'].idxmax()
                        best_ros_val = float(grp_p.loc[best_ros_cat, 'ros'])
                        
                        answer_text = (
                            f"Tổng lợi nhuận hoạt động kinh doanh đạt {vi_format_num(total_prof)} VND trên tổng doanh thu {vi_format_num(total_rev)} VND, "
                            f"tương ứng ROS trung bình toàn doanh nghiệp là {ros}%. "
                            f"Nhóm đạt tỷ suất ROS cao nhất là '{best_ros_cat}' với mức {best_ros_val}%."
                        )
                        metrics_used = {'total_profit': total_prof, 'ros': ros, 'best_ros_cat': best_ros_cat}
                    else:
                        answer_text = f"Tổng lợi nhuận kinh doanh đạt {vi_format_num(total_prof)} VND, ROS đạt {ros}%."
                        metrics_used = {'total_profit': total_prof, 'ros': ros}
                else:
                    answer_text = f"Tổng lợi nhuận kinh doanh đạt {vi_format_num(total_prof)} VND, tỷ suất ROS toàn công ty đạt {ros}%."
                    metrics_used = {'total_profit': total_prof, 'ros': ros}
                    
            # 4. Questions regarding trends or time (thời gian, tháng, xu hướng, tăng trưởng)
            elif any(k in q_lower for k in ['tháng', 'thời gian', 'xu hướng', 'tăng trưởng', 'thời điểm']) and date_col and rev_col and date_col in df.columns and rev_col in df.columns:
                df_temp = df.copy()
                df_temp['YM'] = pd.to_datetime(df_temp[date_col], errors='coerce').dt.strftime('%Y-%m')
                monthly = df_temp.groupby('YM')[rev_col].sum()
                if len(monthly) > 1:
                    peak_m = monthly.idxmax()
                    peak_v = float(monthly.max())
                    low_m = monthly.idxmin()
                    low_v = float(monthly.min())
                    answer_text = (
                        f"Trong toàn bộ giai đoạn theo dõi, tháng có doanh thu đỉnh điểm là {peak_m} đạt {vi_format_num(peak_v)} VND. "
                        f"Tháng có doanh thu thấp nhất là {low_m} với {vi_format_num(low_v)} VND."
                    )
                    metrics_used = {'peak_month': peak_m, 'peak_revenue': peak_v, 'low_month': low_m, 'low_revenue': low_v}
                else:
                    answer_text = f"Dữ liệu có tổng doanh thu {vi_format_num(df[rev_col].sum())} VND trải dài trong kỳ."
                    metrics_used = {'total_rev': float(df[rev_col].sum())}
            
            # Default fallback if question did not match above
            if not answer_text:
                if rev_col and rev_col in df.columns:
                    total_r = float(df[rev_col].sum())
                    avg_r = float(df[rev_col].mean())
                    count_r = len(df)
                    answer_text = (
                        f"Dựa trên phân tích toàn bộ {count_r} giao dịch: tổng giá trị đạt {vi_format_num(total_r)} VND, "
                        f"bình quân mỗi giao dịch đạt {vi_format_num(avg_r)} VND."
                    )
                    metrics_used = {'total_revenue': total_r, 'average_order': avg_r, 'count': count_r}
                else:
                    answer_text = f"Tập dữ liệu ghi nhận tổng cộng {len(df)} dòng dữ liệu hợp lệ được xử lý."
                    metrics_used = {'count': len(df)}
                    
            answers.append({
                'question': q_clean,
                'answer': answer_text,
                'metrics': metrics_used
            })
            
        return answers
