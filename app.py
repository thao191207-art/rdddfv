import os
import io
import json
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response, Query
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np

try:
    from core.data_loader import (
        load_data_from_bytes,
        load_google_sheet_by_url,
        load_sample_dataset
    )
    from core.cleaner import DataCleaner
    from core.analyzer import DataAnalyzer
    from core.reporter import ReportEngine
    from core.exporter import export_to_csv, export_to_excel, export_to_pdf
    from core.ai_assistant import query_llm_business_advisor
except ImportError:
    from data_loader import (
        load_data_from_bytes,
        load_google_sheet_by_url,
        load_sample_dataset
    )
    from cleaner import DataCleaner
    from analyzer import DataAnalyzer
    from reporter import ReportEngine
    from exporter import export_to_csv, export_to_excel, export_to_pdf
    from ai_assistant import query_llm_business_advisor

app = FastAPI(title="Không gian phân tích", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory workspace session state
class WorkspaceSession:
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.current_step: int = 1
        self.step_unlocked: Dict[int, bool] = {1: True, 2: False, 3: False, 4: False}
        self.business_context: Dict[str, Any] = {
            'business_type': '',
            'additional_info': '',
            'questions': [],
            'ai_consultation': None,
            'user_clarification': ''
        }
        self.source_metadata: Optional[Dict[str, Any]] = None
        self.raw_df: Optional[pd.DataFrame] = None
        self.cleaned_df: Optional[pd.DataFrame] = None
        self.cleaner: Optional[DataCleaner] = None
        self.column_roles: Dict[str, str] = {}
        self.analysis_results: Optional[Dict[str, Any]] = None
        self.report_engine: Optional[ReportEngine] = None
        self.last_dashboard_cache: Optional[Dict[str, Any]] = None

session = WorkspaceSession()

# -------------------------------------------------------------
# Step 1: Connect APIs
# -------------------------------------------------------------

@app.get("/api/state")
def get_workspace_state():
    """Return the current step, unlocked statuses, and source summary."""
    return {
        'current_step': session.current_step,
        'step_unlocked': session.step_unlocked,
        'has_data': session.raw_df is not None,
        'source_name': session.source_metadata.get('filename') if session.source_metadata else None,
        'row_count': len(session.cleaned_df if session.cleaned_df is not None else (session.raw_df if session.raw_df is not None else [])),
        'business_context': session.business_context,
        'column_roles': session.column_roles,
        'audit_log': session.cleaner.audit_log if session.cleaner else []
    }

@app.post("/api/connect/form")
def save_business_form(payload: Dict[str, Any]):
    """Validate business context form (reject empty, check 1-8 questions)."""
    biz_type = payload.get('business_type', '').strip()
    add_info = payload.get('additional_info', '').strip()
    questions_raw = payload.get('questions', '')
    
    if not biz_type:
        raise HTTPException(status_code=400, detail="Vui lòng nhập 'Loại hình doanh nghiệp'.")
        
    if isinstance(questions_raw, str):
        lines = [line.strip() for line in questions_raw.splitlines() if line.strip()]
    elif isinstance(questions_raw, list):
        lines = [str(q).strip() for q in questions_raw if str(q).strip()]
    else:
        lines = []
        
    if not lines:
        raise HTTPException(status_code=400, detail="Vui lòng nhập ít nhất một câu hỏi hoặc vấn đề cần phân tích.")
    if len(lines) > 8:
        raise HTTPException(status_code=400, detail="Số lượng câu hỏi tối đa là 8 dòng. Bạn đã nhập quá số lượng cho phép.")
        
    session.business_context['business_type'] = biz_type
    session.business_context['additional_info'] = add_info
    session.business_context['questions'] = lines
    
    return {
        'success': True,
        'message': "Đã lưu ngữ cảnh bài toán kinh doanh.",
        'business_context': session.business_context
    }

@app.post("/api/connect/ai-consult")
def ai_consult():
    """Send business context and questions to AI / LLM Advisor."""
    biz = session.business_context.get('business_type', '')
    add = session.business_context.get('additional_info', '')
    qs = session.business_context.get('questions', [])
    
    if not biz or not qs:
        raise HTTPException(status_code=400, detail="Vui lòng hoàn thành biểu mẫu bài toán kinh doanh trước khi trao đổi với AI.")
        
    ai_resp = query_llm_business_advisor(biz, add, qs)
    session.business_context['ai_consultation'] = ai_resp
    return ai_resp

@app.post("/api/connect/ai-clarify")
def ai_clarify(payload: Dict[str, str]):
    """Store user's clarifying answer and include in analysis context."""
    user_reply = payload.get('clarification', '').strip()
    session.business_context['user_clarification'] = user_reply
    return {'success': True, 'message': 'Đã ghi nhận thông tin làm rõ từ người dùng.'}

@app.post("/api/connect/upload")
async def upload_file(file: UploadFile = File(...)):
    """Handle CSV/TSV file upload with encoding & delimiter detection."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Tệp tải lên không có dữ liệu.")
        
    try:
        session.reset() # Complete fresh session
        df, meta = load_data_from_bytes(content, filename=file.filename)
        session.raw_df = df
        session.cleaned_df = df.copy()
        session.cleaner = DataCleaner(df)
        session.source_metadata = meta
        session.column_roles = session.cleaner.detect_column_roles()
        return {
            'success': True,
            'metadata': meta,
            'column_roles': session.column_roles
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/connect/sample")
def load_sample(payload: Dict[str, str]):
    """Load sample datasets: 'marketing_sales' or 'retail_logistics'."""
    key = payload.get('key', 'marketing_sales')
    try:
        session.reset() # Complete fresh session
        df, meta = load_sample_dataset(key)
        session.raw_df = df
        session.cleaned_df = df.copy()
        session.cleaner = DataCleaner(df)
        session.source_metadata = meta
        session.column_roles = session.cleaner.detect_column_roles()
        return {
            'success': True,
            'metadata': meta,
            'column_roles': session.column_roles
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/connect/sheets")
def load_sheets(payload: Dict[str, str]):
    """Connect public Google Sheet URL."""
    url = payload.get('url', '').strip()
    try:
        session.reset() # Complete fresh session
        df, meta = load_google_sheet_by_url(url)
        session.raw_df = df
        session.cleaned_df = df.copy()
        session.cleaner = DataCleaner(df)
        session.source_metadata = meta
        session.column_roles = session.cleaner.detect_column_roles()
        return {
            'success': True,
            'metadata': meta,
            'column_roles': session.column_roles
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/connect/complete")
def complete_step_1():
    """Verify Step 1 completion and unlock Step 2."""
    if session.raw_df is None or session.raw_df.empty:
        raise HTTPException(status_code=400, detail="Chưa có dữ liệu nào được kết nối. Vui lòng tải tệp hoặc chọn dữ liệu mẫu.")
    if not session.business_context.get('business_type'):
        # Auto fill default if user bypassed
        session.business_context['business_type'] = "Doanh nghiệp thương mại & dịch vụ"
    if not session.business_context.get('questions'):
        session.business_context['questions'] = [
            "Doanh thu theo nhóm sản phẩm nào cao nhất?",
            "Tỷ suất lợi nhuận trên doanh thu (ROS) đạt bao nhiêu?",
            "Xu hướng tăng trưởng qua các kỳ biến động ra sao?"
        ]
        
    session.step_unlocked[2] = True
    session.current_step = 2
    return {'success': True, 'current_step': 2}

# -------------------------------------------------------------
# Step 2: Clean and Normalize APIs
# -------------------------------------------------------------

@app.get("/api/clean/issues")
def get_clean_issues():
    """Get detected quality issues in current dataframe."""
    if session.cleaner is None:
        raise HTTPException(status_code=400, detail="Chưa tải tập dữ liệu.")
    issues = session.cleaner.detect_issues()
    preview = session.cleaner.df.head(20).fillna('').to_dict(orient='records')
    roles = session.cleaner.detect_column_roles()
    return {
        'issues': issues,
        'preview': preview,
        'columns': list(session.cleaner.df.columns),
        'audit_log': session.cleaner.audit_log,
        'column_roles': session.column_roles or roles
    }

@app.post("/api/clean/action")
def apply_cleaning_action(payload: Dict[str, Any]):
    """Apply single cleaning action (fill, drop rows, drop col, standardize, trim)."""
    if session.cleaner is None:
        raise HTTPException(status_code=400, detail="Chưa tải tập dữ liệu.")
    action_type = payload.get('action_type')
    column = payload.get('column')
    params = payload.get('params', {})
    
    try:
        log_entry = session.cleaner.apply_action(action_type, column, params)
        session.cleaned_df = session.cleaner.df.copy()
        issues = session.cleaner.detect_issues()
        preview = session.cleaner.df.head(20).fillna('').to_dict(orient='records')
        return {
            'success': True,
            'log_entry': log_entry,
            'issues': issues,
            'preview': preview,
            'columns': list(session.cleaner.df.columns),
            'audit_log': session.cleaner.audit_log
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/clean/auto")
def auto_clean():
    """Apply automatic clean pipeline."""
    if session.cleaner is None:
        raise HTTPException(status_code=400, detail="Chưa tải tập dữ liệu.")
    logs = session.cleaner.auto_clean_all()
    session.cleaned_df = session.cleaner.df.copy()
    issues = session.cleaner.detect_issues()
    preview = session.cleaner.df.head(20).fillna('').to_dict(orient='records')
    return {
        'success': True,
        'logs': logs,
        'issues': issues,
        'preview': preview,
        'audit_log': session.cleaner.audit_log
    }

@app.post("/api/clean/roles")
def update_column_roles(payload: Dict[str, str]):
    """Map columns to semantic roles."""
    session.column_roles.update(payload)
    return {'success': True, 'column_roles': session.column_roles}

@app.post("/api/clean/complete")
def complete_step_2():
    """Verify Step 2, update cleaned dataset, and unlock Step 3."""
    if session.cleaner is None or session.cleaner.df.empty:
        raise HTTPException(status_code=400, detail="Không có dữ liệu hợp lệ sau khi làm sạch.")
        
    session.cleaned_df = session.cleaner.df.copy()
    # Ensure role mapping is present
    roles = session.cleaner.detect_column_roles()
    for k, v in roles.items():
        if k not in session.column_roles or not session.column_roles[k]:
            session.column_roles[k] = v
            
    # Check that required roles are mapped
    if not session.column_roles.get('revenue_col'):
        raise HTTPException(status_code=400, detail="Chưa xác định cột 'Doanh thu'. Vui lòng chọn cột doanh thu ở bảng ánh xạ vai trò cột.")
        
    session.step_unlocked[3] = True
    session.current_step = 3
    return {'success': True, 'current_step': 3, 'column_roles': session.column_roles}

# -------------------------------------------------------------
# Step 3: Analyze APIs
# -------------------------------------------------------------

@app.post("/api/analyze/run")
def run_analysis():
    """Compute real statistics, correlations, anomalies, and answers to business questions."""
    if session.cleaned_df is None or session.cleaned_df.empty:
        raise HTTPException(status_code=400, detail="Dữ liệu chưa được làm sạch.")
        
    analyzer = DataAnalyzer(session.cleaned_df, session.column_roles, session.business_context)
    summary_stats = analyzer.compute_summary_stats()
    correlations = analyzer.compute_correlations()
    anomalies = analyzer.compute_anomalies()
    
    questions = session.business_context.get('questions', [])
    answers = analyzer.answer_business_questions(questions)
    
    session.analysis_results = {
        'summary_stats': summary_stats,
        'correlations': correlations,
        'anomalies': anomalies,
        'answers': answers
    }
    
    # Initialize report engine
    session.report_engine = ReportEngine(session.cleaned_df, session.column_roles, session.business_context)
    session.step_unlocked[4] = True
    session.current_step = 4
    
    return {
        'success': True,
        'analysis_results': session.analysis_results,
        'current_step': 4
    }

# -------------------------------------------------------------
# Step 4: Report and Dashboard APIs
# -------------------------------------------------------------

@app.get("/api/report/options")
def get_report_options():
    """Get available month and group filter options."""
    if session.report_engine is None:
        if session.cleaned_df is not None:
            session.report_engine = ReportEngine(session.cleaned_df, session.column_roles, session.business_context)
        else:
            raise HTTPException(status_code=400, detail="Chưa hoàn thành phân tích dữ liệu.")
    return session.report_engine.get_filter_options()

@app.get("/api/report/summary-strip")
def get_summary_strip():
    """Get horizontal summary KPI strip."""
    if session.report_engine is None:
        if session.cleaned_df is not None:
            session.report_engine = ReportEngine(session.cleaned_df, session.column_roles, session.business_context)
        else:
            raise HTTPException(status_code=400, detail="Chưa có báo cáo.")
    return session.report_engine.compute_summary_strip()

@app.get("/api/report/dashboard")
def get_dashboard_data(month: Optional[str] = Query(None), group: Optional[str] = Query(None)):
    """Get executive dashboard layout matching reference image with selected month & group."""
    if session.report_engine is None:
        if session.cleaned_df is not None:
            session.report_engine = ReportEngine(session.cleaned_df, session.column_roles, session.business_context)
        else:
            raise HTTPException(status_code=400, detail="Chưa hoàn thành phân tích.")
            
    dash = session.report_engine.compute_dashboard(selected_ym=month, selected_group=group)
    session.last_dashboard_cache = dash
    return dash

# -------------------------------------------------------------
# Export APIs
# -------------------------------------------------------------

@app.get("/api/export/csv")
def export_csv_file():
    """Download cleaned dataset as CSV."""
    if session.cleaned_df is None or session.cleaned_df.empty:
        raise HTTPException(status_code=400, detail="Chưa có dữ liệu làm sạch.")
    csv_bytes = export_to_csv(session.cleaned_df)
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="du_lieu_da_lam_sach.csv"'}
    )

@app.get("/api/export/excel")
def export_excel_file():
    """Download professional Excel report with native embedded charts."""
    if session.cleaned_df is None or session.cleaned_df.empty:
        raise HTTPException(status_code=400, detail="Chưa có dữ liệu làm sạch.")
    if session.last_dashboard_cache is None:
        if session.report_engine:
            session.last_dashboard_cache = session.report_engine.compute_dashboard()
        else:
            raise HTTPException(status_code=400, detail="Chưa có báo cáo phân tích.")
            
    audit = session.cleaner.audit_log if session.cleaner else []
    excel_bytes = export_to_excel(session.cleaned_df, session.last_dashboard_cache, audit)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="Bao_cao_Khong_gian_phan_tich.xlsx"'}
    )

@app.get("/api/export/pdf")
def export_pdf_file():
    """Download PDF report with all charts and analysis."""
    if session.cleaned_df is None or session.cleaned_df.empty:
        raise HTTPException(status_code=400, detail="Chưa có dữ liệu làm sạch.")
    if session.last_dashboard_cache is None:
        if session.report_engine:
            session.last_dashboard_cache = session.report_engine.compute_dashboard()
        else:
            raise HTTPException(status_code=400, detail="Chưa có báo cáo phân tích.")
            
    summary_strip = session.report_engine.compute_summary_strip()
    pdf_bytes = export_to_pdf(session.last_dashboard_cache, summary_strip, session.business_context)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="Bao_cao_Khong_gian_phan_tich.pdf"'}
    )

@app.post("/api/step/navigate")
def navigate_step(payload: Dict[str, int]):
    """Navigate to an unlocked step."""
    step = payload.get('step', 1)
    if not session.step_unlocked.get(step, False):
        raise HTTPException(status_code=403, detail=f"Bước {step} đang bị khóa. Bạn cần hoàn thành bước trước đó.")
    session.current_step = step
    return {'current_step': step}

@app.post("/api/reset")
def reset_workspace():
    """Reset the entire workspace session."""
    session.reset()
    return {'success': True, 'message': 'Đã làm mới không gian phân tích.'}

from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
if not os.path.exists(STATIC_DIR):
    STATIC_DIR = os.path.join(BASE_DIR, "public", "static")

# -------------------------------------------------------------
# Static files and root index serving
# -------------------------------------------------------------

@app.get("/static/style.css")
@app.get("/style.css")
def serve_css():
    for p in ["static/style.css", "public/static/style.css", "style.css"]:
        full_p = os.path.join(BASE_DIR, p) if not os.path.isabs(p) else p
        if os.path.exists(full_p):
            return FileResponse(full_p, media_type="text/css")
        if os.path.exists(p):
            return FileResponse(p, media_type="text/css")
    raise HTTPException(status_code=404, detail="CSS file not found")

@app.get("/static/app.js")
@app.get("/app.js")
def serve_js():
    for p in ["static/app.js", "public/static/app.js", "app.js"]:
        full_p = os.path.join(BASE_DIR, p) if not os.path.isabs(p) else p
        if os.path.exists(full_p):
            return FileResponse(full_p, media_type="application/javascript")
        if os.path.exists(p):
            return FileResponse(p, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="JS file not found")

@app.get("/static/{file_path:path}")
def get_static_file(file_path: str):
    for candidate in [os.path.join(STATIC_DIR, file_path), os.path.join(BASE_DIR, file_path), file_path]:
        if os.path.exists(candidate) and os.path.isfile(candidate):
            media_type = "text/css" if file_path.endswith(".css") else ("application/javascript" if file_path.endswith(".js") else None)
            return FileResponse(candidate, media_type=media_type)
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    for candidate in [os.path.join(STATIC_DIR, "index.html"), os.path.join(BASE_DIR, "index.html"), "index.html", "static/index.html"]:
        if os.path.exists(candidate) and os.path.isfile(candidate):
            with open(candidate, "r", encoding="utf-8") as f:
                return f.read()
    return "<h1>Không gian phân tích (Analysis Workspace)</h1><p>Đang tải ứng dụng...</p>"

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
