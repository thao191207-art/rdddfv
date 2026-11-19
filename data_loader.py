import os
import io
import re
import csv
import pandas as pd
import requests
from typing import Tuple, Dict, Any, Optional

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

def detect_encoding(raw_bytes: bytes) -> str:
    """Detect encoding with priority for UTF-8-sig and UTF-8, then CP1258 (Vietnamese)."""
    if raw_bytes.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig'
    try:
        raw_bytes.decode('utf-8')
        return 'utf-8'
    except UnicodeDecodeError:
        pass
    try:
        raw_bytes.decode('cp1258')
        return 'cp1258'
    except UnicodeDecodeError:
        pass
    return 'latin1'

def detect_delimiter(sample_text: str) -> str:
    """Detect delimiter: comma, semicolon, tab, or pipe."""
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample_text[:4096], delimiters=[',', ';', '\t', '|'])
        return dialect.delimiter
    except Exception:
        first_line = sample_text.splitlines()[0] if sample_text else ""
        for delim in [',', ';', '\t', '|']:
            if delim in first_line:
                return delim
        return ','

def detect_column_types(df: pd.DataFrame) -> Dict[str, str]:
    """Detect column type: 'numeric', 'datetime', or 'categorical'."""
    col_types = {}
    for col in df.columns:
        series = df[col].dropna()
        if series.empty:
            col_types[col] = 'categorical'
            continue
        if pd.api.types.is_numeric_dtype(series):
            col_types[col] = 'numeric'
        elif pd.api.types.is_datetime64_any_dtype(series):
            col_types[col] = 'datetime'
        else:
            sample = series.head(50).astype(str).str.strip()
            # Check if looks like dates
            is_date = False
            try:
                # Try parsing if strings match common date patterns
                if sample.str.contains(r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}').mean() > 0.6 or \
                   sample.str.contains(r'^\d{1,2}[-/]\d{1,2}[-/]\d{4}').mean() > 0.6:
                    pd.to_datetime(sample, errors='coerce')
                    is_date = True
            except Exception:
                is_date = False
            
            if is_date:
                col_types[col] = 'datetime'
            else:
                # Check if looks like numeric with formatting (e.g. 1.000.000 or 1,000.00 or $500 or 25%)
                cleaned_sample = sample.str.replace(r'[\sđ₫$€£%.,]', '', regex=True)
                if cleaned_sample.str.isnumeric().mean() > 0.8:
                    col_types[col] = 'numeric'
                else:
                    col_types[col] = 'categorical'
    return col_types

def load_data_from_bytes(file_bytes: bytes, filename: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Parse CSV/TSV bytes, detecting encoding and delimiter."""
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"Dung lượng tệp vượt quá giới hạn 50MB ({len(file_bytes) / (1024*1024):.1f}MB).")
    
    encoding = detect_encoding(file_bytes[:10000])
    text_sample = file_bytes[:8192].decode(encoding, errors='replace')
    delimiter = detect_delimiter(text_sample)
    
    try:
        df = pd.read_csv(
            io.BytesIO(file_bytes),
            encoding=encoding,
            sep=delimiter,
            dtype=str
        )
    except Exception as e:
        raise ValueError(f"Lỗi đọc định dạng tệp: {str(e)}")
        
    if df.empty:
        raise ValueError("Tệp dữ liệu trống, không chứa bản ghi nào.")
        
    col_types = detect_column_types(df)
    
    metadata = {
        'filename': filename,
        'row_count': len(df),
        'column_count': len(df.columns),
        'columns': list(df.columns),
        'column_types': col_types,
        'encoding': encoding,
        'delimiter': delimiter,
        'preview': df.head(20).fillna('').to_dict(orient='records')
    }
    return df, metadata

def load_google_sheet_by_url(url: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Extract spreadsheet ID and gid from Google Sheets URL and fetch public CSV."""
    if not url or not isinstance(url, str):
        raise ValueError("Vui lòng nhập đường link Google Sheet hợp lệ.")
        
    id_match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    if not id_match:
        raise ValueError("Không tìm thấy Spreadsheet ID hợp lệ trong liên kết Google Sheets.")
    sheet_id = id_match.group(1)
    
    gid_match = re.search(r'[#&?]gid=([0-9]+)', url)
    gid = gid_match.group(1) if gid_match else '0'
    
    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    
    try:
        resp = requests.get(export_url, timeout=12)
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Không thể kết nối đến Google Sheets: {str(e)}")
        
    if resp.status_code == 404:
        raise ValueError("Không tìm thấy trang tính Google Sheet. Vui lòng kiểm tra lại URL.")
    elif resp.status_code in [401, 403] or 'ServiceLogin' in resp.url or 'accounts.google.com' in resp.text:
        raise ValueError("Google Sheet này chưa được chia sẻ công khai. Vui lòng mở quyền 'Bất kỳ ai có đường liên kết đều có thể xem' trong Google Sheets.")
    elif resp.status_code != 200:
        raise ValueError(f"Lỗi khi tải trang tính (mã lỗi {resp.status_code}). Vui lòng đảm bảo bảng tính ở chế độ công khai.")
        
    content_type = resp.headers.get('content-type', '')
    if 'text/html' in content_type and '<!DOCTYPE html>' in resp.text:
        raise ValueError("Google Sheet yêu cầu quyền đăng nhập hoặc chưa được chia sẻ công khai.")
        
    return load_data_from_bytes(resp.content, filename=f"GoogleSheet_{sheet_id[:8]}")

def load_sample_dataset(dataset_key: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Load sample datasets stored in data/ directory."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, 'data')
    if not os.path.exists(data_dir):
        data_dir = 'data'
        
    if dataset_key == 'marketing_sales' or dataset_key == 'doanh_thu_marketing':
        candidates = ['data/doanh_thu_marketing.csv', 'doanh_thu_marketing.csv', os.path.join(base_dir, 'data', 'doanh_thu_marketing.csv')]
        path = next((c for c in candidates if os.path.exists(c)), 'data/doanh_thu_marketing.csv')
        display_name = 'Doanh thu và marketing'
    elif dataset_key == 'retail_logistics' or dataset_key == 'ban_le_logistics':
        candidates = ['data/ban_le_logistics.csv', 'ban_le_logistics.csv', os.path.join(base_dir, 'data', 'ban_le_logistics.csv')]
        path = next((c for c in candidates if os.path.exists(c)), 'data/ban_le_logistics.csv')
        display_name = 'Bán lẻ đa kênh & Logistics'
    else:
        raise ValueError(f"Không tìm thấy tập dữ liệu mẫu: '{dataset_key}'")
        
    if not os.path.exists(path):
        raise FileNotFoundError(f"Tệp dữ liệu mẫu không tồn tại tại đường dẫn: {path}")
        
    with open(path, 'rb') as f:
        content = f.read()
    df, meta = load_data_from_bytes(content, filename=display_name)
    meta['is_sample'] = True
    meta['sample_key'] = dataset_key
    return df, meta
