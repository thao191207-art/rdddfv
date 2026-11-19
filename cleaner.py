import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

class DataCleaner:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.audit_log: List[Dict[str, Any]] = []
        
    def detect_issues(self) -> Dict[str, Any]:
        """Detect all data quality issues: missing values, duplicates, dates, numeric in text, casing."""
        df = self.df
        total_rows = len(df)
        issues = {
            'total_rows': total_rows,
            'total_columns': len(df.columns),
            'missing_values': {},
            'duplicates_count': int(df.duplicated().sum()),
            'numeric_as_text': {},
            'date_inconsistencies': {},
            'casing_inconsistencies': {},
            'summary_count': 0
        }
        
        # 1. Missing values
        for col in df.columns:
            # Treat empty strings or whitespace-only as missing
            is_empty_str = df[col].astype(str).str.strip().isin(['', 'nan', 'null', 'None', 'NA', 'N/A'])
            missing_count = int(df[col].isna().sum() + is_empty_str.sum())
            if missing_count > 0:
                issues['missing_values'][col] = {
                    'count': missing_count,
                    'percentage': round((missing_count / total_rows) * 100, 2)
                }
                issues['summary_count'] += 1
                
        if issues['duplicates_count'] > 0:
            issues['summary_count'] += 1
            
        # 2. Check each column for numeric-in-text, dates, and casing
        for col in df.columns:
            series = df[col].dropna().astype(str).str.strip()
            if series.empty:
                continue
                
            # Check numeric as text
            # E.g. contains currency symbols (đ, $, €), %, commas or dots used as thousand separators
            num_pattern_count = 0
            sample_non_num = 0
            for val in series.head(100):
                v = val.strip()
                if not v:
                    continue
                # check if has symbols but is essentially numeric
                cleaned_v = re.sub(r'[\sđ₫$€£%]', '', v)
                # replace Vietnamese thousand separator (dot) or comma
                if re.match(r'^-?\d{1,3}([.,]\d{3})+([.,]\d+)?$', cleaned_v) or \
                   re.match(r'^-?\d+([.,]\d+)?%$', v) or \
                   (any(sym in v for sym in ['đ', '₫', '$', '€', 'đ/']) and re.search(r'\d', v)):
                    num_pattern_count += 1
                elif not v.replace('.', '', 1).replace('-', '', 1).isdigit():
                    sample_non_num += 1
                    
            if num_pattern_count > 0 and num_pattern_count >= sample_non_num * 0.3:
                issues['numeric_as_text'][col] = {
                    'detected_count': num_pattern_count,
                    'examples': series.head(3).tolist()
                }
                issues['summary_count'] += 1
                
            # Check date formats
            # Look for date-like strings
            date_matches = 0
            formats_found = set()
            for val in series.head(50):
                v = val.strip()
                if re.match(r'^\d{4}-\d{1,2}-\d{1,2}', v):
                    formats_found.add('YYYY-MM-DD')
                    date_matches += 1
                elif re.match(r'^\d{1,2}/\d{1,2}/\d{4}', v):
                    formats_found.add('DD/MM/YYYY')
                    date_matches += 1
                elif re.match(r'^\d{1,2}-\d{1,2}-\d{4}', v):
                    formats_found.add('DD-MM-YYYY')
                    date_matches += 1
                    
            if len(formats_found) > 1 or (date_matches > 10 and 'YYYY-MM-DD' not in formats_found):
                issues['date_inconsistencies'][col] = {
                    'formats_detected': list(formats_found),
                    'examples': series.head(3).tolist()
                }
                issues['summary_count'] += 1
                
            # Check whitespace and casing in categorical columns
            # only for non-numeric, non-date
            if col not in issues['numeric_as_text'] and date_matches < 10:
                has_whitespace = series.str.contains(r'^\s+|\s+$|\s{2,}', regex=True).sum()
                unique_vals = series.unique()
                lower_map = {}
                casing_duplicates = 0
                for u in unique_vals:
                    norm = u.strip().lower()
                    if norm in lower_map and lower_map[norm] != u.strip():
                        casing_duplicates += 1
                    else:
                        lower_map[norm] = u.strip()
                        
                if has_whitespace > 0 or casing_duplicates > 0:
                    issues['casing_inconsistencies'][col] = {
                        'whitespace_count': int(has_whitespace),
                        'casing_variations_count': casing_duplicates,
                        'examples': series.head(3).tolist()
                    }
                    issues['summary_count'] += 1
                    
        return issues

    def apply_action(self, action_type: str, column: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Apply a cleaning action with before/after tracking and audit logging."""
        params = params or {}
        before_rows = len(self.df)
        before_cols = len(self.df.columns)
        action_name_vi = ""
        details_vi = ""
        
        if action_type == 'drop_duplicates':
            dup_count = int(self.df.duplicated().sum())
            self.df = self.df.drop_duplicates().reset_index(drop=True)
            action_name_vi = "Xóa dòng trùng lặp"
            details_vi = f"Đã loại bỏ {dup_count} dòng trùng lặp hoàn toàn."
            
        elif action_type == 'drop_missing_rows':
            if column and column in self.df.columns:
                mask = self.df[column].isna() | self.df[column].astype(str).str.strip().isin(['', 'nan', 'null', 'None', 'NA', 'N/A'])
                dropped = int(mask.sum())
                self.df = self.df[~mask].reset_index(drop=True)
                action_name_vi = f"Xóa dòng thiếu ở cột '{column}'"
                details_vi = f"Đã xóa {dropped} dòng có giá trị trống."
            else:
                before = len(self.df)
                self.df = self.df.dropna().reset_index(drop=True)
                dropped = before - len(self.df)
                action_name_vi = "Xóa tất cả dòng chứa giá trị trống"
                details_vi = f"Đã xóa {dropped} dòng chứa ô trống."
                
        elif action_type == 'fill_missing':
            method = params.get('method', 'zero')
            custom_val = params.get('value', 0)
            if column and column in self.df.columns:
                series = self.df[column].replace(['', 'nan', 'null', 'None', 'NA', 'N/A'], np.nan)
                fill_val = None
                
                # Check if column is numeric
                numeric_series = pd.to_numeric(series.astype(str).str.replace(r'[\sđ₫$€£%,]', '', regex=True), errors='coerce')
                
                if method == 'mean' and not numeric_series.dropna().empty:
                    fill_val = round(numeric_series.mean(), 2)
                elif method == 'median' and not numeric_series.dropna().empty:
                    fill_val = round(numeric_series.median(), 2)
                elif method == 'mode':
                    mode_val = series.mode()
                    fill_val = mode_val[0] if not mode_val.empty else "N/A"
                elif method == 'zero':
                    fill_val = 0
                elif method == 'custom':
                    fill_val = custom_val
                else:
                    fill_val = 0
                    
                missing_cnt = int(series.isna().sum())
                self.df[column] = series.fillna(fill_val)
                action_name_vi = f"Điền giá trị thiếu ở cột '{column}'"
                details_vi = f"Đã điền {missing_cnt} giá trị trống bằng phương pháp '{method}' (giá trị: {fill_val})."
                
        elif action_type == 'drop_column':
            if column and column in self.df.columns:
                self.df = self.df.drop(columns=[column])
                action_name_vi = f"Xóa cột '{column}'"
                details_vi = f"Đã loại bỏ cột '{column}' khỏi tập dữ liệu."
                
        elif action_type == 'standardize_numeric':
            if column and column in self.df.columns:
                # Clean currency, spaces, comma/dots
                def clean_num(val):
                    if pd.isna(val):
                        return np.nan
                    v = str(val).strip()
                    if not v or v in ['nan', 'null', 'None']:
                        return np.nan
                    is_pct = '%' in v
                    # remove symbols
                    v = re.sub(r'[\sđ₫$€£]', '', v)
                    v = v.replace('%', '')
                    # If formatted like 1.234.567 or 1,234,567
                    if re.match(r'^-?\d{1,3}(\.\d{3})+(,\d+)?$', v):
                        v = v.replace('.', '').replace(',', '.')
                    elif re.match(r'^-?\d{1,3}(,\d{3})+(\.\d+)?$', v):
                        v = v.replace(',', '')
                    try:
                        num = float(v)
                        return num / 100.0 if is_pct else num
                    except ValueError:
                        return np.nan
                        
                self.df[column] = self.df[column].apply(clean_num)
                action_name_vi = f"Chuẩn hóa số ở cột '{column}'"
                details_vi = f"Đã chuyển đổi văn bản sang số, loại bỏ ký hiệu tiền tệ và phân cách hàng nghìn."
                
        elif action_type == 'standardize_date':
            target_fmt = params.get('format', '%Y-%m-%d')
            if column and column in self.df.columns:
                def parse_date(val):
                    if pd.isna(val):
                        return np.nan
                    v = str(val).strip()
                    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S']:
                        try:
                            dt = datetime.strptime(v.split(' ')[0], fmt)
                            return dt.strftime(target_fmt)
                        except ValueError:
                            continue
                    try:
                        return pd.to_datetime(v).strftime(target_fmt)
                    except Exception:
                        return v
                        
                self.df[column] = self.df[column].apply(parse_date)
                action_name_vi = f"Chuẩn hóa ngày ở cột '{column}'"
                details_vi = f"Đã thống nhất định dạng ngày về chuẩn {target_fmt}."
                
        elif action_type == 'trim_and_case':
            case_type = params.get('case', 'trim')  # 'trim', 'title', 'upper', 'lower'
            if column and column in self.df.columns:
                s = self.df[column].astype(str).str.strip()
                # replace multiple spaces with single space
                s = s.str.replace(r'\s+', ' ', regex=True)
                if case_type == 'title':
                    s = s.str.title()
                elif case_type == 'upper':
                    s = s.str.upper()
                elif case_type == 'lower':
                    s = s.str.lower()
                self.df[column] = s
                action_name_vi = f"Chuẩn hóa khoảng trắng & chữ viết cột '{column}'"
                details_vi = f"Đã cắt bỏ khoảng trắng thừa và chuyển đổi kiểu chữ ({case_type})."
        else:
            raise ValueError(f"Hành động không xác định: {action_type}")
            
        after_rows = len(self.df)
        after_cols = len(self.df.columns)
        
        log_entry = {
            'id': len(self.audit_log) + 1,
            'timestamp': datetime.now().strftime('%H:%M:%S %d/%m/%Y'),
            'action_type': action_type,
            'column': column or 'Tất cả',
            'action_name': action_name_vi,
            'details': details_vi,
            'before_rows': before_rows,
            'after_rows': after_rows,
            'before_cols': before_cols,
            'after_cols': after_cols,
            'rows_changed': abs(before_rows - after_rows)
        }
        self.audit_log.append(log_entry)
        return log_entry

    def auto_clean_all(self) -> List[Dict[str, Any]]:
        """Automatically clean common obvious issues: remove duplicates, trim whitespace, standardize numbers/dates."""
        logs = []
        # 1. Duplicates
        if self.df.duplicated().sum() > 0:
            logs.append(self.apply_action('drop_duplicates'))
            
        # 2. Inspect and fix numeric columns
        for col in self.df.columns:
            series = self.df[col].dropna().astype(str).str.strip()
            if series.empty:
                continue
            # If values have currency or percentage and contain digits
            has_currency_symbols = series.str.contains(r'[đ₫$€£%]', regex=True) & series.str.contains(r'\d', regex=True)
            if has_currency_symbols.sum() > len(series) * 0.3:
                logs.append(self.apply_action('standardize_numeric', column=col))
            # Or if it's already purely numeric strings, convert to float/int
            elif pd.to_numeric(series, errors='coerce').notna().mean() > 0.8:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
                
        # 3. Trim whitespace in text columns
        for col in self.df.columns:
            if self.df[col].dtype == object:
                sample = self.df[col].dropna().astype(str)
                if sample.str.contains(r'^\s+|\s+$|\s{2,}', regex=True).sum() > 0:
                    logs.append(self.apply_action('trim_and_case', column=col, params={'case': 'trim'}))
                    
        return logs

    def detect_column_roles(self) -> Dict[str, str]:
        """Auto-detect semantic column roles: date_col, category_col, revenue_col, profit_col, order_col, cost_col, channel_col."""
        df = self.df
        roles: Dict[str, str] = {
            'date_col': '',
            'category_col': '',
            'revenue_col': '',
            'profit_col': '',
            'order_col': '',
            'cost_col': '',
            'channel_col': ''
        }
        
        for col in df.columns:
            col_lower = col.lower().strip()
            # Date
            if not roles['date_col'] and any(kw in col_lower for kw in ['ngày', 'ngay', 'date', 'thời gian', 'thoi_gian', 'time']):
                roles['date_col'] = col
            # Order ID
            elif not roles['order_col'] and any(kw in col_lower for kw in ['mã đơn', 'ma_don', 'order', 'vận đơn', 'van_don', 'id', 'mã']):
                roles['order_col'] = col
            # Revenue
            elif not roles['revenue_col'] and any(kw in col_lower for kw in ['doanh thu', 'doanh_thu', 'revenue', 'tổng tiền', 'tong_tien', 'thành tiền', 'sales']):
                roles['revenue_col'] = col
            # Profit
            elif not roles['profit_col'] and any(kw in col_lower for kw in ['lợi nhuận', 'loi_nhuan', 'profit', 'lãi', 'lai']):
                roles['profit_col'] = col
            # Cost
            elif not roles['cost_col'] and any(kw in col_lower for kw in ['chi phí', 'chi_phi', 'cost', 'giá vốn', 'gia_von']):
                roles['cost_col'] = col
            # Product Group / Category
            elif not roles['category_col'] and any(kw in col_lower for kw in ['nhóm sản phẩm', 'nhom_san_pham', 'sản phẩm', 'ngành hàng', 'nganh_hang', 'category', 'nhóm', 'loại']):
                roles['category_col'] = col
            # Channel
            elif not roles['channel_col'] and any(kw in col_lower for kw in ['kênh', 'kenh', 'channel', 'khu vực', 'khu_vuc', 'region']):
                roles['channel_col'] = col
                
        # Fallbacks if not found:
        if not roles['revenue_col']:
            # Pick first numeric column with highest sum
            numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
            if numeric_cols:
                sums = {c: df[c].sum() for c in numeric_cols}
                roles['revenue_col'] = max(sums, key=sums.get)
                
        if not roles['category_col']:
            # Pick categorical column with 2 to 20 unique values
            cat_cols = [c for c in df.columns if c not in roles.values() and df[c].dtype == object and 2 <= df[c].nunique() <= 20]
            if cat_cols:
                roles['category_col'] = cat_cols[0]
                
        return roles
