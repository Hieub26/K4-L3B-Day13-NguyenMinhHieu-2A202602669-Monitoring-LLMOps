# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Minh Hiếu
- **MSSV:** 2A202602669
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/Hieub26/K4-L3B-Day13-NguyenMinhHieu-2A202602669-Monitoring-LLMOps
- **Commit SHA cuối:** 69fbf1a
- **Challenge ID:** day13-k4-l3b-monitoring-llmops-v1
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602669`


## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Đạt tối đa sau khi bind correlation ID, enrich context và đăng ký PII scrubber |
| `validate_dashboard.py` | 6/6 panel | 6/6 panel | Đạt chuẩn schema contract 6 panel |
| `pytest` | 22 passed | 31 passed | Pass 100% (bổ sung test middleware headers, CCCD, thẻ, passport, address, child obs) |
| Số traces hợp lệ | 10 | 35 traces | Đã tạo 35 traces thực tế có span tree cha - con trên Langfuse cá nhân |

| Số PII leak | 0 | 0 | 0 rò rỉ PII trong toàn bộ log sinh ra |
| Latency P95 / TTFT P95 | ~1814ms / 50ms | ~2180ms / 50ms | Độ trễ ổn định qua các lần load test |
| Retrieval success rate | 100% | 100% | Retrieval hoạt động ổn định trong điều kiện chuẩn |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:**
  Nhận qua HTTP header `x-request-id`, nếu client không gửi sẽ tự sinh theo định dạng chuẩn `req-<8-hex>` (`f"req-{uuid.uuid4().hex[:8]}"`). Trước mỗi request, `CorrelationIdMiddleware` gọi `clear_contextvars()` để tránh ô nhiễm context giữa các request đồng thời, sau đó `bind_contextvars(correlation_id=correlation_id)` và lưu vào `request.state.correlation_id`. Khi trả về response, middleware đính kèm các header `x-request-id` và `x-response-time-ms`.
- **Các metadata được ghi vào structured log:**
  Ghi nhận đầy đủ: `ts` (ISO-8601 UTC), `level`, `service`, `event`, `correlation_id`, `user_id_hash` (băm SHA-256 12 ký tự), `session_id`, `feature`, `model`, `env`, `payload` (chỉ chứa preview đã scrub và rút gọn), cùng các chỉ số vận hành gồm `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:**
  Xây dựng processor `scrub_event` đệ quy qua các dictionary, list, string trong event log và đăng ký vào pipeline structlog ngay trước `JsonlFileProcessor` và `JSONRenderer`. Định nghĩa tập regex chặt chẽ trong `PII_PATTERNS` để nhận diện Email, SĐT Việt Nam các định dạng, CCCD (12 số), Thẻ thanh toán (16 số), Hộ chiếu và Địa chỉ VN, thay thế bằng `[REDACTED_<TYPE>]` trước khi dữ liệu được serialize hoặc ghi xuống file `data/logs.jsonl`.
- **Cách kiểm chứng kết quả:**
  Chạy bộ kiểm thử tự động `python -m pytest -q` (30/30 passed) và công cụ thẩm định log `python scripts/validate_logs.py` (đạt điểm tuyệt đối 100/100, xác nhận 0 record thiếu trường bắt buộc, 0 record thiếu context enrichment, và 0 PII leak).


## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
  Các traces được gửi trực tiếp tới project cá nhân `day13-k4-l3b-2A202602669` trên Langfuse Cloud thông qua API keys riêng trong `.env`. Mỗi trace mang `trace_name="day13-agent-request"`, tags `["lab", feature, model]`, và `user_id_hash` đã băm tương ứng với phiên người dùng.
- **Cấu trúc root/retrieval/generation observations:**
  Cây span tuân thủ chuẩn quan sát phân tầng:
  - Root observation: `lab-agent-run` (as_type=`agent`).
  - Child observation 1: `retrieval` (as_type=`retriever`), đo riêng độ trễ và trạng thái truy xuất context.
  - Child observation 2: `generation` (as_type=`generation`), bọc LLM call và ghi nhận model `claude-sonnet-4-5`, prompt liên kết, `usage_details` (input/output tokens), `cost_details` (USD), và `ttft_ms`.
- **Cách nối trace với log:**
  `correlation_id` (định dạng `req-<8-hex>`) được truyền vào `propagate_attributes(metadata={"correlation_id": correlation_id})`. Nhờ vậy, metadata của trace trên Langfuse chứa chính xác `correlation_id` trùng khớp với trường `correlation_id` trong từng dòng structured log `data/logs.jsonl`.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** Version 1 gắn labels `['baseline', 'production']`.
- **Version/label candidate:** Version 2 gắn label `['candidate']` (bổ sung chỉ dẫn: *"Keep responses concise and prioritize retrieved context."*).
- **Trace ID của mỗi version:**
  - Request dùng Version 1 (Baseline): correlation ID `req-f856de7c`
  - Request dùng Version 2 (Candidate - promoted): correlation ID `req-b47042a9`
  - Request dùng Version 1 (Sau khi Rollback): correlation ID `req-38d8ce02`
- **Cách promote và rollback `production`:**
  - **Promote**: Chuyển label `production` trỏ sang Version 2 trên Langfuse UI hoặc gọi `client.update_prompt(name="day13-chat", version=2, new_labels=["candidate", "production"])`.
  - **Rollback**: Chuyển label `production` quay về Version 1 (`client.update_prompt(name="day13-chat", version=1, new_labels=["baseline", "production"])`). Toàn bộ hệ thống rollback tức thì mà không cần deploy lại code.


## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
  Dashboard thời gian thực được xây dựng chuẩn theo contract `config/dashboard.yaml` tại endpoint `/dashboard` (cửa sổ 60 phút, refresh 30 giây, nguồn dữ liệu từ `data/logs.jsonl`):
  1. **Latency**: Đo P50, P95, P99 và TTFT P95 từ `response_sent.latency_ms/ttft_ms` (Đơn vị: ms, Ngưỡng cảnh báo: P95 $\le$ 3000ms).
  2. **Traffic**: Đo thông lượng và tổng số request từ `request_received` (Đơn vị: requests_per_minute, Ngưỡng: rate $\ge$ 1 req/phút).
  3. **Errors**: Đo tỷ lệ lỗi và tỷ lệ thành công của Retrieval (`error_rate_pct`, phân bố `error_type`, `retrieval_success_rate_pct`, Đơn vị: %, Ngưỡng: error rate $\le$ 2%, retrieval $\ge$ 90%).
  4. **Cost**: Tổng hợp chi phí inference mô hình từ `response_sent.cost_usd` (Đơn vị: USD, Ngưỡng ngân sách: total $\le$ $2.5).
  5. **Tokens**: Thống kê số lượng token đầu vào và đầu ra từ `response_sent.tokens_in/tokens_out` (Đơn vị: tokens, Ngưỡng: trung bình tokens_out $\le$ 500).
  6. **Quality**: Điểm chất lượng câu trả lời heuristic từ `response_sent.quality_score` (Đơn vị: score [0-1], Ngưỡng mục tiêu: avg $\ge$ 0.75).
- **SLO và lý do chọn:**
  - Mục tiêu: **99.5%** request thành công và có `latency_ms <= 3000ms` trong cửa sổ trượt 28 ngày (`primary_slo.name: fast_successful_requests`).
  - SLI: Số good requests (`event == "response_sent" and latency_ms <= 3000`) trên tổng số request nhận vào (`event == "request_received"`).
  - Lý do chọn: 3000ms là ngưỡng vàng cho tương tác hội thoại trực tiếp với LLM trước khi người dùng cảm thấy bị đơ hoặc timeout giao diện; 99.5% đảm bảo độ sẵn sàng cao của dịch vụ AI.
- **Cách tính error budget:**
  - Với SLO 99.5% trong 28 ngày, Error Budget được phép lỗi là: $100\% - 99.5\% = 0.5\%$.
  - Công thức: $\text{Allowed Bad Requests} = \text{Total Requests} \times 0.5\%$.
  - Ví dụ: Nếu workload có 10,000 request trong 28 ngày thì tối đa **50 request** được phép bị lỗi (HTTP 5xx) hoặc có độ trễ chậm hơn ngưỡng 3000ms.
- **Ba alert và runbook tương ứng:**
  1. `HighLatencyP95` (Warning): `p95(latency_ms) > 3000ms` kéo dài 5 phút. Kênh: Slack `#k4-l3b-alerts`. Runbook (`docs/alerts.md#alert-1`): Mở panel Latency kiểm tra P95/P99 $\rightarrow$ lọc correlation ID chậm trong log $\rightarrow$ xem span tree trên Langfuse để khoanh vùng retrieval hay generation bị nghẽn $\rightarrow$ rollback prompt hoặc giảm tải.
  2. `HighErrorRate` (Critical): `error_rate_pct > 2%` kéo dài 3 phút. Kênh: Slack `#k4-l3b-alerts`. Runbook (`docs/alerts.md#alert-2`): Mở panel Errors kiểm tra loại lỗi $\rightarrow$ đọc `payload.detail` trong log `request_failed` $\rightarrow$ kiểm tra trace trên Langfuse để xem stack trace $\rightarrow$ disable incident injection hoặc restart container.
  3. `RetrievalFailureSpike` (Warning): `retrieval_success_rate_pct < 90%` kéo dài 5 phút. Kênh: Slack `#k4-l3b-alerts`. Runbook (`docs/alerts.md#alert-3`): Kiểm tra panel Errors $\rightarrow$ lọc log có `tool_name == "retrieval"` và `tool_success == false` $\rightarrow$ mở trace xem mã lỗi vector store $\rightarrow$ kích hoạt fallback corpus nội bộ và khôi phục database.


## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (Cohort K4)
- **Khoảng thời gian điều tra:** 10:58:00 – 11:00:00 (30/09/2026)
- **Triệu chứng từ metrics:** Panel Latency trên dashboard ghi nhận P95 tăng vọt lên mức 3,669ms – 6,941ms+ (vượt ngưỡng threshold 3,000ms, trạng thái chuyển sang ALERTING). Error rate vẫn giữ mức 0%, cho thấy hệ thống không sập nhưng bị nghẽn độ trễ nghiêm trọng.
- **Log line và correlation ID liên quan:**
  - `correlation_id`: `req-77059c22` (và `req-f99d2aef`)
  - Log event `response_sent`:
    ```json
    {"service": "api", "latency_ms": 2654, "ttft_ms": 50, "tokens_in": 35, "tokens_out": 105, "cost_usd": 0.00168, "quality_score": 0.8, "tool_name": "retrieval", "tool_success": true, "event": "response_sent", "correlation_id": "req-77059c22", "feature": "monitoring", "model": "claude-sonnet-4-5", "session_id": "k4-l3b-challenge-s01", "level": "info", "ts": "2026-09-30T03:58:52.240799Z"}
    ```
- **Trace ID và span gây ảnh hưởng:**
  - Langfuse Trace ID: `6711f765822630cfbabf86acbc3caf8f` (hoặc `9c9799ccfa30ce97b9356307644d6ea3`)
  - Chi tiết phân rã thời gian:
    - Span `lab-agent-run`: tổng độ trễ `2.654s`
    - Span `generation`: chỉ chiếm `0.152s`
    - Span `retrieval`: kéo dài tới `2.501s` (chiếm hơn 94% tổng thời gian request)
- **Root cause:**
  Sự cố bắt nguồn từ bước **Retrieval (RAG retrieval component)**. Khi nhận các câu hỏi liên quan đến tính năng `monitoring`, module `retrieve` bị chậm đột biến (`rag_slow` gây trễ 2.5 giây khi truy vấn corpus/vector store), trong khi LLM generation vẫn phản hồi rất nhanh (chỉ mất ~150ms).
- **Fix action:**
  Vô hiệu hóa sự cố bằng lệnh `python scripts/inject_incident.py --disable` (gọi endpoint `/incidents/rag_slow/disable`). Kiểm tra lại vector database, khởi động lại service kết nối hoặc tạm thời chuyển hướng sang bộ nhớ đệm (cache) cho các tài liệu domain `monitoring`.
- **Preventive measure:**
  1. **Alerting**: Kích hoạt alert `HighLatencyP95` (với điều kiện `p95(latency_ms) > 3000ms` trong 5 phút) để gửi cảnh báo tự động về Slack `#k4-l3b-alerts`.
  2. **Timeout & Circuit Breaker**: Thiết lập timeout cho retrieval (ví dụ: tối đa 1.5 giây), nếu vượt quá timeout sẽ tự động fallback về câu trả lời tổng quát hoặc dùng cached context, tránh làm treo luồng chat của người dùng.
  3. **Monitoring chi tiết**: Theo dõi riêng metric latency của span `retrieval` trên Langfuse để phát hiện sớm hiện tượng suy giảm hiệu năng trước khi vi phạm SLO toàn hệ thống.


## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
  Thiết kế pipeline lọc PII đệ quy (`scrub_event`) đặt ngay trước JSON renderer và JsonlFileProcessor trong Structlog, đồng thời đặt `capture_input=False, capture_output=False` trên Langfuse observations và chỉ lưu bản preview đã qua `summarize_text`. Quyết định này giúp loại bỏ hoàn toàn nguy cơ rò rỉ PII vào cả 2 nguồn lưu trữ độc lập (log file và trace cloud) mà vẫn giữ nguyên context cần thiết để điều tra sự cố.
- **Một lỗi/blocker đã gặp:**
  Xung đột thứ tự khớp mẫu regex giữa thẻ thanh toán (16 số) và CCCD (12 số): chuỗi thẻ tín dụng có dấu gạch ngang bị tiền tố CCCD khớp trước dẫn đến kết quả che giấu bị phân mảnh dạng `[REDACTED_CCCD]-3456`.
- **Cách tìm nguyên nhân và xử lý:**
  Viết unit test chi tiết trong `tests/test_pii.py` và phát hiện ra lỗi thông qua test failure. Đã xử lý bằng cách đưa `credit_card` lên trước `cccd` trong từ điển `PII_PATTERNS`, đồng thời siết chặt định dạng CCCD theo nhóm 3-3-3-3 hoặc 12 số liên tục để không nhận nhầm nhóm 4-4-4 của thẻ.
- **Cách hiểu luồng Metrics → Logs → Traces:**
  - **Metrics** là giác quan phát hiện triệu chứng: cho biết hệ thống đang xấu ở đâu và bắt đầu từ khung giờ nào (ví dụ: P95 latency vượt ngưỡng 3,000ms lúc 10:58).
  - **Logs** là công cụ định vị đối tượng: dựa vào khoảng thời gian của Metric để lọc tìm các dòng log lỗi/chậm và lấy ra mã định danh duy nhất `correlation_id` (ví dụ: `req-77059c22`).
  - **Traces** là kính hiển vi mổ xẻ nguyên nhân: tìm trace có cùng `correlation_id` trên Langfuse, phân tích waterfall của từng span con để tìm chính xác dòng code/dịch vụ gây lỗi (chứng minh span `retrieval` chiếm 2.5s trên tổng số 2.65s).
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  Prompt chi phối trực tiếp đến độ dài token, độ trễ và chi phí. Quản lý prompt version theo nhãn (`production`, `candidate`) cho phép đội ngũ kỹ thuật thử nghiệm prompt mới và thực hiện rollback ngay tức thì khi phát hiện triệu chứng bất thường mà không cần restart hay rebuild service. SLO và Error budget đặt ra ranh giới định lượng giữa mục tiêu trải nghiệm người dùng và tốc độ cập nhật hệ thống.
- **Điều quan trọng nhất đã học:**
  Tư duy vận hành LLMOps có hệ thống: điều tra sự cố bằng chuỗi bằng chứng không thể chối cãi (Metrics $\rightarrow$ Logs $\rightarrow$ Traces $\rightarrow$ Root Cause) thay vì phỏng đoán mò mẫm.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**
  Do bài lab sử dụng mock component để mô phỏng môi trường lab, chưa tích hợp persistent vector DB phân tán thực tế.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.

