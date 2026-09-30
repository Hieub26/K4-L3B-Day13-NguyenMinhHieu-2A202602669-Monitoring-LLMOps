# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: `response_sent.latency_ms` (ngưỡng P95 $\le$ 3000ms theo primary SLO)
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` duy trì trong 5 phút
- Ảnh hưởng tới người dùng: Người dùng phải chờ quá 3 giây để nhận phản hồi, giao diện có nguy cơ timeout hoặc giảm trải nghiệm.
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel **Latency** để xác nhận P50, P95, P99 và TTFT nhằm khoanh vùng thời điểm bắt đầu chậm.
  2. Lọc file `data/logs.jsonl` trong khung giờ đó, chọn một dòng `response_sent` có `latency_ms > 3000` và trích xuất `correlation_id`.
  3. Mở trace có cùng `correlation_id` trên Langfuse, so sánh thời gian của span `retrieval` và `generation` để xác định bước nào gây nghẽn.
- Mitigation tạm thời: Nếu do prompt mới làm LLM sinh quá dài $\rightarrow$ rollback prompt về version cũ; nếu do RAG vector store chậm $\rightarrow$ tạm thời chuyển sang cached context hoặc restart service retrieval; nếu quá tải traffic $\rightarrow$ bật rate limiting.
- Owner: `student-2A202602669`

## Alert 2

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `3m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Tỷ lệ lỗi toàn hệ thống (`error_rate_pct` theo guardrails $\le$ 2%)
- Điều kiện và thời gian duy trì: `count(event == "request_failed") / count(event == "request_received") * 100 > 2%` duy trì trong 3 phút
- Ảnh hưởng tới người dùng: Nhiều yêu cầu chat bị lỗi 500 hoặc gián đoạn, người dùng không nhận được câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel **Errors** để xem error rate và phân bố `error_type` (RuntimeError, Timeout, ValueError, v.v.).
  2. Tra cứu `data/logs.jsonl` tìm các event `request_failed` gần nhất, đọc trường `error_type` và `payload.detail`, lấy `correlation_id`.
  3. Mở trace tương ứng trên Langfuse để xem span nào bị đánh dấu đỏ/error và stack trace chi tiết.
- Mitigation tạm thời: Nếu do incident injection $\rightarrow$ vô hiệu hóa incident bằng API `/incidents/{name}/disable`; nếu do prompt syntax/variable lỗi $\rightarrow$ rollback prompt; nếu do backend crash $\rightarrow$ tự động restart container/pod qua healthcheck.
- Owner: `student-2A202602669`

## Alert 3

- Tên: `RetrievalFailureSpike`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: `retrieval_success_rate_pct` (ngưỡng tối thiểu $\ge$ 90% theo guardrails)
- Điều kiện và thời gian duy trì: `retrieval_success_rate_pct < 90%` trong vòng 5 phút
- Ảnh hưởng tới người dùng: Mô hình không nhận được tài liệu tham khảo chính xác từ cơ sở tri thức, dẫn đến câu trả lời hallucination, chung chung hoặc sai lệch chính sách.
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel **Errors** kiểm tra tỷ lệ `tool_success_rate_pct` của retrieval.
  2. Lọc trong log `data/logs.jsonl` các dòng có `tool_name == "retrieval"` và `tool_success == false`.
  3. Mở trace trên Langfuse, kiểm tra span `retrieval` để xem mã lỗi kết nối, timeout hay query format không hợp lệ.
- Mitigation tạm thời: Kích hoạt fallback retrieval corpus tĩnh nội bộ; kiểm tra trạng thái vector database/kho tài liệu và khôi phục kết nối.
- Owner: `student-2A202602669`

