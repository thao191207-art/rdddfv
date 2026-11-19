# Không gian phân tích (Analysis Workspace)

Ứng dụng phân tích dữ liệu kinh doanh thông minh và bảng điều khiển điều hành (Executive Analytics Dashboard) được xây dựng theo chuẩn chuyên nghiệp, hỗ trợ tiếng Việt đầy đủ với quy trình chuẩn 4 bước: **Kết nối → Làm sạch → Phân tích → Báo cáo**.

Dữ liệu được tính toán số học chính xác tuyệt đối từ tập dữ liệu thực của người dùng, giao diện khớp chuẩn bố cục dashboard điều hành đối chiếu theo tháng và nhóm hàng, tích hợp trao đổi bài toán với AI và xuất tệp đa định dạng (PDF, Excel tích hợp biểu đồ native, CSV).

---

## 1. Tính năng nổi bật

### Bước 1 — Kết nối dữ liệu (Connect Data)
- **Biểu mẫu thiết lập ngữ cảnh kinh doanh**:
  - *Loại hình doanh nghiệp* (Bắt buộc, ví dụ: Bán lẻ, B2B SaaS, Logistics...)
  - *Thông tin bổ sung* (Không bắt buộc)
  - *Vấn đề cần phân tích* (Bắt buộc, tối đa 8 câu hỏi, kiểm tra số dòng và từ chối nếu để trống)
- **Bảng trao đổi yêu cầu với AI (AI Advisor Panel)**:
  - Tự động gọi LLM (qua biến môi trường `GEMINI_API_KEY` hoặc `OPENAI_API_KEY`) để tóm tắt mục tiêu, chỉ ra các chiều dữ liệu còn thiếu, và đề xuất 2-3 câu hỏi làm rõ.
  - Lưu trữ câu trả lời làm rõ của người dùng và đưa vào ngữ cảnh phân tích.
  - Có cơ chế suy luận dự phòng thông minh (Contextual Fallback Engine) nếu chưa cấu hình khóa API.
- **Kết nối Google Sheets**:
  - Nhập URL Google Sheets công khai, tự động trích xuất `spreadsheet_id` và `gid`, tải bảng tính qua định dạng CSV xuất bản.
  - Xử lý thông báo lỗi chi tiết khi bảng tính chưa được chia sẻ công khai.
- **Tải lên tệp CSV/TSV**:
  - Tự động nhận diện bảng mã (UTF-8, UTF-8 có BOM, CP1258 tiếng Việt, Latin-1) và dấu phân cách (dấu phẩy, chấm phẩy, tab, pipe).
  - Giới hạn kích thước tệp 50 MB, có thanh tiến trình tải.
- **Dữ liệu mẫu thực tế (Sample Datasets)**:
  - *Doanh thu và marketing* (`doanh_thu_marketing.csv`): 1.366 dòng, khớp chính xác số liệu đối chiếu trên dashboard mẫu (Tổng doanh thu 20.717.175.575 VND, tháng T10 đạt 1.666.023.008 VND, 5 nhóm mặt hàng, chu kỳ 12 tháng từ T11-2018 đến T10-2019, ROS 22%, tăng trưởng -3%).
  - *Bán lẻ đa kênh & Logistics* (`ban_le_logistics.csv`): 1.502 dòng thực tế với cấu trúc cột khác biệt hoàn toàn (Mã vận đơn, Ngành hàng, Tổng tiền, Lợi nhuận ròng, Kênh phân phối, Khu vực, Thời gian giao hàng).
- **Khóa quy trình (Step Locking)**: Các bước 2, 3, 4 được khóa cho đến khi hoàn tất bước trước đó. Thẻ trạng thái ở sidebar cập nhật thời gian thực tên nguồn dữ liệu và số lượng dòng.

### Bước 2 — Làm sạch và chuẩn hóa (Clean & Normalize)
- **Tự động quét và phát hiện các vấn đề dữ liệu**:
  - Giá trị trống (Missing values) theo từng cột kèm tỷ lệ phần trăm.
  - Dòng trùng lặp hoàn toàn (Duplicate rows).
  - Định dạng ngày không nhất quán (YYYY-MM-DD, DD/MM/YYYY...).
  - Cột số bị lưu dạng văn bản (chứa dấu phân cách hàng nghìn, tiền tệ `đ`, `₫`, `$`, `%`).
  - Khoảng trắng thừa và sai lệch kiểu chữ (Title Case, UPPERCASE, lowercase).
- **Hành động xử lý tương tác**: Điền giá trị (Mean, Median, Mode, 0, tùy chỉnh), xóa dòng trống, xóa cột, chuẩn hóa số, chuẩn hóa ngày, cắt khoảng trắng và đổi kiểu chữ.
- **Nhật ký làm sạch (Audit Log)**: Ghi lại từng bước xử lý kèm thời gian, chi tiết thao tác, số dòng trước và sau khi thay đổi.
- **Ánh xạ vai trò cột (Column Role Mapping)**: Tự động phát hiện hoặc cho phép người dùng tùy biến gán vai trò cột: Cột Doanh thu, Cột Nhóm sản phẩm, Cột Ngày tháng, Cột Lợi nhuận HĐKD, Cột Mã đơn, Cột Kênh bán... đảm bảo chạy đúng trên bất kỳ tệp dữ liệu nào.

### Bước 3 — Phân tích (Analyze)
- **Thống kê mô tả toàn diện**: Đếm số dòng, tổng, trung bình, trung vị, min, max, độ lệch chuẩn (Std) cho mọi biến số định lượng; phân phối tần suất và nhóm hàng đầu cho các biến định tính.
- **Ma trận tương quan (Correlation Matrix)** giữa các biến định lượng.
- **Phát hiện giao dịch dị biệt (Outliers)** theo quy tắc 3 Sigma và khoảng tứ phân vị (IQR).
- **Giải quyết bài toán kinh doanh**: Ánh xạ từng câu hỏi kinh doanh từ Bước 1 sang thuật toán tính toán cụ thể với số liệu đối chiếu chính xác.

### Bước 4 — Báo cáo điều hành & Xuất tệp (Report & Export)
- **Thanh tổng số ngang (Summary Strip)**: Tổng doanh thu, Trung bình, Trung vị, Nhỏ nhất, Lớn nhất, Số dòng dữ liệu, Nhóm hàng dẫn đầu theo chuẩn định dạng tiếng Việt (dấu chấm phân cách hàng nghìn, dấu phẩy thập phân).
- **Dashboard điều hành tái lập chính xác bố cục chuẩn**:
  - *Hàng 1*: Bộ chọn tháng báo cáo "CHỌN THÁNG BC" (ví dụ T10 - Năm 2019) → Cột thẻ KPI xếp chồng (Tổng doanh thu, Doanh thu tháng hiện tại, Tổng đơn hàng, Đơn hàng tháng hiện tại); Biểu đồ cột Doanh thu theo nhóm SP (với số liệu Millions hiển thị bên trong từng cột bar và màu riêng biệt từng nhóm); Biểu đồ cột Lợi nhuận HĐKD theo nhóm SP; Hộp KPI Tăng trưởng doanh thu MoM (-3%); Biểu đồ Donut ROS toàn công ty (22%).
  - *Hàng 2*: Bộ chọn nhóm hàng "CHỌN NHÓM SP" (ví dụ: Nhóm chuối, Nhóm khoai...) → Biểu đồ cột Doanh thu của nhóm hàng qua 12 tháng (màu cam, đơn vị Millions); Biểu đồ đường Tăng trưởng doanh thu từng nhóm hàng (lấy mốc kỳ gốc tháng đầu tiên = 100%, có nhãn % từng điểm); Biểu đồ Donut ROS riêng của nhóm hàng được chọn.
  - *Chuyển đổi kiểu biểu đồ (Chart Type Selector)*: Cho phép đổi linh hoạt giữa Cột (Column), Thanh ngang (Bar), Đường (Line), Vùng (Area), Tròn (Pie).
  - *Bình luận phân tích chuyên sâu (Written Analysis) dưới mỗi biểu đồ*: Đoạn văn tiếng Việt (2-5 câu) nêu rõ số liệu then chốt, nhóm cao/thấp nhất, mức chênh lệch, xu hướng biến động và liên hệ trực tiếp đến bài toán kinh doanh. Tất cả con số đều được kiểm chứng chặt chẽ với dữ liệu tính toán.
  - *Bảng tổng hợp phát hiện trọng yếu*: Phát hiện, Chỉ số, Giá trị, Đối chiếu so sánh, Hành động khuyến nghị.
- **Xuất tệp**:
  - **Xuất PDF**: Báo cáo nguyên bản đầy đủ bảng tổng quan, chỉ số điều hành, biểu đồ phân tích và khuyến nghị.
  - **Xuất Excel (.xlsx)**: File Excel chuyên nghiệp gồm Sheet Báo cáo & KPI, dữ liệu bảng và các **biểu đồ native embedded của Excel** (Column, Line...), kèm Sheet Dữ liệu đã làm sạch và Sheet Nhật ký xử lý.
  - **Xuất CSV**: Tải về dữ liệu đã làm sạch chuẩn UTF-8 BOM.

---

## 2. Cài đặt và Khởi chạy

### Yêu cầu hệ thống
- Python 3.9+ (Đã kiểm nghiệm hoàn hảo trên Python 3.14).
- Trình duyệt web hiện đại (Chrome, Edge, Firefox, Safari).

### Cài đặt thư viện cần thiết
```bash
python -m pip install fastapi uvicorn pandas numpy openpyxl xlsxwriter reportlab requests pytest httpx
```

### Thiết lập biến môi trường (Tùy chọn)
Nếu muốn kích hoạt LLM trực tuyến cho bảng tư vấn AI, bạn có thể thiết lập:
```bash
# Trên Windows PowerShell:
$env:GEMINI_API_KEY="your-gemini-api-key"
# hoặc
$env:OPENAI_API_KEY="your-openai-api-key"

# Trên Linux / macOS:
export GEMINI_API_KEY="your-gemini-api-key"
```
*(Nếu không cấu hình khóa API, ứng dụng sẽ tự động kích hoạt bộ máy chuyên gia phân tích ngữ cảnh dự phòng thông minh, đảm bảo không bao giờ bị gián đoạn hay phát sinh lỗi).*

### Khởi chạy ứng dụng trên Localhost
Chạy lệnh duy nhất:
```bash
python app.py
```
Mở trình duyệt web và truy cập:
👉 **`http://localhost:8000`** (hoặc `http://127.0.0.1:8000`)

---

## 3. Chạy kiểm thử tự động (Automated Testing)

Bộ kiểm thử tự động gồm 10 bài test toàn diện kiểm tra tính toán độc lập, độ chính xác số học, kiểm tra làm sạch, phân tích và kiểm thử end-to-end:
```bash
python -m pytest tests -v
```

### Các tệp kiểm thử:
- `tests/test_accuracy.py`: Kiểm chứng độc lập số học từng KPI từ tệp gốc và so sánh nghiêm ngặt với kết quả của hệ thống.
- `tests/test_cleaner.py`: Kiểm tra các hàm làm sạch, nhận diện ô trống, dòng trùng, cắt khoảng trắng và nhận diện vai trò cột.
- `tests/test_analyzer.py`: Kiểm tra độ chính xác thống kê, ma trận tương quan và thuật toán trả lời câu hỏi bài toán kinh doanh.
- `tests/test_arbitrary_schema.py`: Kiểm tra việc thích ứng tự động với lược đồ cột tùy ý bất kỳ (`ban_le_logistics.csv`).
- `tests/test_e2e.py`: Kiểm thử toàn trình từ nạp dữ liệu, làm sạch, phân tích đến xuất file PDF, Excel và CSV.

---

## 4. Cấu trúc thư mục dự án

```
.
├── app.py                      # FastAPI server & API endpoints
├── core/
│   ├── data_loader.py          # Xử lý tệp CSV/TSV, Google Sheets & tập dữ liệu mẫu
│   ├── cleaner.py              # Bộ phát hiện lỗi, chuẩn hóa & ánh xạ vai trò cột
│   ├── analyzer.py             # Bộ tính toán thống kê, tương quan, dị biệt & giải câu hỏi
│   ├── reporter.py             # Bộ engine báo cáo, tính toán KPI & sinh đoạn phân tích
│   ├── exporter.py             # Bộ xuất file PDF, Excel (biểu đồ native) & CSV
│   └── ai_assistant.py         # Module tư vấn bài toán kinh doanh với AI
├── data/
│   ├── doanh_thu_marketing.csv # Dữ liệu thực nghiệm mẫu đối chiếu với hình tham khảo
│   └── ban_le_logistics.csv    # Dữ liệu bán lẻ đa kênh & logistics
├── static/
│   ├── index.html              # Giao diện chính Single-Page Application tiếng Việt
│   ├── app.js                  # Toàn bộ logic tương tác phía client & vẽ biểu đồ Chart.js
│   └── style.css               # Phong cách giao diện chuẩn bảng điều khiển điều hành
├── tests/
│   ├── test_accuracy.py        # Kiểm thử tính toán số học độc lập
│   ├── test_analyzer.py        # Kiểm thử tính toán thống kê
│   ├── test_arbitrary_schema.py# Kiểm thử lược đồ dữ liệu tùy ý
│   ├── test_cleaner.py         # Kiểm thử các thao tác làm sạch
│   └── test_e2e.py             # Kiểm thử toàn trình (End-to-End)
├── scripts/
│   └── generate_datasets.py    # Script sinh tập dữ liệu mẫu chuẩn số học
└── README.md                   # Tài liệu hướng dẫn sử dụng
```
