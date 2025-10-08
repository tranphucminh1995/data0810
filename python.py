# app_phan_tich_kinh_doanh.py (Đã chỉnh sửa)

import streamlit as st
import pandas as pd
import numpy as np
import io
import re
from google import genai
from google.genai.errors import APIError
from docx import Document 

# --- Cấu hình Trang Streamlit ---
st.set_page_config(
    page_title="App Đánh giá Phương án Kinh doanh",
    layout="wide"
)

st.title("Ứng dụng Đánh giá Phương án Kinh doanh 📈")
st.markdown("Sử dụng AI để trích xuất dữ liệu, tính toán dòng tiền và đánh giá hiệu quả dự án đầu tư từ file Word.")

# ------------------------------------------------------------------------------
# KHẮC PHỤC LỖI: Thêm chức năng nhập API Key qua Sidebar nếu không tìm thấy
# ------------------------------------------------------------------------------
def get_gemini_client():
    """Tạo và trả về client Gemini, ưu tiên từ Secrets, sau đó là Sidebar."""
    
    # 1. Ưu tiên lấy từ Streamlit Secrets
    api_key = st.secrets.get("GEMINI_API_KEY")
    
    # 2. Nếu không có trong Secrets, tạo ô nhập liệu trong Sidebar
    if not api_key:
        with st.sidebar:
            st.subheader("Cấu hình API Key")
            st.warning("⚠️ Không tìm thấy GEMINI_API_KEY trong Streamlit Secrets.")
            api_key = st.text_input(
                "Nhập Khóa API Gemini của bạn:", 
                type="password",
                help="Bạn có thể lấy khóa này từ Google AI Studio."
            )
            st.caption("Khóa API sẽ không được lưu.")
    
    if api_key:
        try:
            return genai.Client(api_key=api_key)
        except Exception as e:
            # Lỗi xảy ra khi khóa API có định dạng sai
            st.error(f"Lỗi khởi tạo Gemini Client: Khóa API không hợp lệ. Chi tiết: {e}")
            return None
    else:
        # Hiển thị lỗi chính trên main page
        st.error("Lỗi: Không tìm thấy Khóa API. Vui lòng cấu hình Khóa 'GEMINI_API_KEY' trong Streamlit Secrets hoặc nhập vào Sidebar.")
        return None

# --- Hàm trích xuất và các hàm tính toán khác (Giữ nguyên) ---

@st.cache_data(show_spinner=False)
def extract_data_from_word_ai(docx_content, client):
    # ... (giữ nguyên code hàm này)
    document = Document(io.BytesIO(docx_content))
    full_text = [para.text for para in document.paragraphs]
    document_text = "\n".join(full_text)
    
    prompt = f"""
    Bạn là một chuyên gia tài chính. Hãy đọc nội dung tài liệu phương án kinh doanh sau và trích xuất **chính xác** các thông số sau đây. 
    Lưu ý: **Vốn đầu tư** là tổng vốn ban đầu (năm 0). **Dòng đời dự án** tính bằng năm (integer). **Doanh thu** và **Chi phí** có thể là một chuỗi giá trị (ví dụ: '[1000, 1100, 1200, ...]') tương ứng với các năm của dự án. **WACC** và **Thuế** là tỷ lệ (ví dụ: 10% -> 0.1). 
    Nếu không tìm thấy thông tin nào, hãy để giá trị đó là 'N/A'.
    
    Trả lời **DUY NHẤT** bằng một đối tượng JSON có cấu trúc như sau:
    {{
        "Vốn đầu tư (VND)": "...",
        "Dòng đời dự án (năm)": "...",
        "Doanh thu (VND/năm)": "[value_year1, value_year2, ...]",
        "Chi phí (VND/năm)": "[value_year1, value_year2, ...]",
        "WACC": "...",
        "Thuế suất": "..."
    }}
    
    Nội dung tài liệu:
    ---
    {document_text[:10000]} 
    ---
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        return response.text
    except APIError as e:
        st.error(f"Lỗi gọi Gemini API: {e}")
        return None
    except Exception as e:
        st.error(f"Lỗi không xác định trong quá trình trích xuất: {e}")
        return None

@st.cache_data
def calculate_project_metrics(initial_investment, cash_flows, wacc, project_life):
    # ... (giữ nguyên code hàm này)
    npv_cash_flows = np.insert(cash_flows, 0, -initial_investment)
    npv_value = np.npv(wacc, npv_cash_flows)
    irr_value = np.irr(npv_cash_flows)
    
    cumulative_cf = np.cumsum(cash_flows)
    pp_value = project_life 
    for i in range(len(cumulative_cf)):
        if cumulative_cf[i] >= initial_investment:
            if i == 0:
                pp_value = initial_investment / cash_flows[0]
            else:
                remaining_investment = initial_investment - cumulative_cf[i-1]
                pp_value = i + (remaining_investment / cash_flows[i])
            break
            
    discounted_cf = cash_flows / [(1 + wacc)**t for t in range(1, project_life + 1)]
    cumulative_discounted_cf = np.cumsum(discounted_cf)
    dpp_value = project_life
    for i in range(len(cumulative_discounted_cf)):
        if cumulative_discounted_cf[i] >= initial_investment:
            if i == 0:
                dpp_value = initial_investment / discounted_cf[0]
            else:
                remaining_investment = initial_investment - cumulative_discounted_cf[i-1]
                dpp_value = i + (remaining_investment / discounted_cf[i])
            break

    return {
        "NPV": npv_value,
        "IRR": irr_value,
        "PP": pp_value,
        "DPP": dpp_value
    }

def get_ai_analysis_project(metrics_data, cash_flow_df, client):
    # ... (giữ nguyên code hàm này)
    metrics_str = pd.Series(metrics_data).to_string()
    cash_flow_str = cash_flow_df.to_markdown(index=False)
    
    prompt = f"""
    Bạn là một chuyên gia tư vấn đầu tư và tài chính dự án chuyên nghiệp. Dựa trên Bảng dòng tiền và các chỉ số hiệu quả dự án sau, hãy đưa ra một đánh giá chuyên sâu và khách quan (khoảng 3-4 đoạn) về tính khả thi và mức độ hấp dẫn của dự án.
    
    1. **Đánh giá chung:** Dự án có đáng đầu tư không? (Dựa trên NPV và IRR so với WACC).
    2. **Đánh giá rủi ro:** Phân tích thời gian hoàn vốn (PP và DPP).
    3. **Khuyến nghị:** Đưa ra kết luận và khuyến nghị (Chấp nhận/Từ chối hoặc cần xem xét thêm).
    
    **Chỉ số Dự án:**
    {metrics_str}
    
    **Bảng Dòng tiền Thuần (Cash Flow):**
    {cash_flow_str}
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text
    except APIError as e:
        return f"Lỗi gọi Gemini API: {e}"
    except Exception as e:
        return f"Đã xảy ra lỗi không xác định: {e}"

# ==============================================================================
#                               LOGIC CHÍNH CỦA APP
# ==============================================================================

client = get_gemini_client()
if client is None:
    st.stop() # Dừng ứng dụng nếu không có API Key hoặc API Key không hợp lệ

# --- Chức năng 1: Tải File & Lọc dữ liệu ---
uploaded_file = st.file_uploader(
    "1. Tải file Word (.docx) chứa Phương án Kinh doanh",
    type=['docx']
)

# Khởi tạo state để lưu dữ liệu đã lọc
if 'extracted_data' not in st.session_state:
    st.session_state['extracted_data'] = None

if uploaded_file is not None:
    st.success(f"Đã tải file: {uploaded_file.name}")
    
    if st.button("🚀 Lọc Thông tin Dự án bằng AI"):
        with st.spinner('AI đang đọc và trích xuất dữ liệu từ file Word...'):
            docx_content = uploaded_file.getvalue()
            # Đảm bảo client đã được khởi tạo trước khi gọi hàm
            if client: 
                json_data = extract_data_from_word_ai(docx_content, client)
                
                if json_data:
                    try:
                        import json
                        extracted_dict = json.loads(json_data)
                        st.session_state['extracted_data'] = extracted_dict
                        st.success("Trích xuất dữ liệu thành công!")
                    except json.JSONDecodeError:
                        st.error("AI không trả lời ở định dạng JSON hợp lệ. Vui lòng thử lại hoặc điều chỉnh file.")
                        st.session_state['extracted_data'] = None
                else:
                    st.error("Không thể trích xuất dữ liệu. Vui lòng kiểm tra API Key hoặc nội dung file.")

if st.session_state['extracted_data']:
    data = st.session_state['extracted_data']
    st.subheader("1.a. Kết quả Trích xuất Dữ liệu của AI")
    st.json(data)
    
    # --- Chuẩn bị dữ liệu cho tính toán ---
    try:
        # Chuyển đổi dữ liệu về dạng số học
        VON_DAU_TU = float(re.sub(r'[^\d.]', '', str(data['Vốn đầu tư (VND)']).split('[')[0]))
        DONG_DOI = int(data['Dòng đời dự án (năm)'])
        WACC = float(data['WACC'])
        THUE = float(data['Thuế suất'])
        
        doanh_thu_str = data['Doanh thu (VND/năm)'].strip()
        chi_phi_str = data['Chi phí (VND/năm)'].strip()
        
        def parse_array(array_str):
            return [float(n) for n in re.findall(r"[-+]?\d*\.\d+|\d+", array_str)]

        DOANH_THU = parse_array(doanh_thu_str)
        CHI_PHI = parse_array(chi_phi_str)
        
        if len(DOANH_THU) != DONG_DOI or len(CHI_PHI) != DONG_DOI:
             st.warning(f"Lỗi dữ liệu: Số lượng năm trong Doanh thu ({len(DOANH_THU)}) hoặc Chi phí ({len(CHI_PHI)}) không khớp với Dòng đời dự án ({DONG_DOI} năm). Vui lòng kiểm tra lại file Word.")
             valid_data = False
        else:
             valid_data = True

    except Exception as e:
        st.error(f"Lỗi chuyển đổi dữ liệu trích xuất sang dạng số: {e}. Vui lòng kiểm tra định dạng dữ liệu AI trả về.")
        valid_data = False

    
    if valid_data:
        # --- Chức năng 2: Xây dựng Bảng Dòng tiền ---
        st.markdown("---")
        st.subheader("2. Xây dựng Bảng Dòng tiền (Cash Flow Statement) 💰")

        years = list(range(1, DONG_DOI + 1))
        
        EBT = np.array(DOANH_THU) - np.array(CHI_PHI)
        THUE_PHAI_NOP = np.where(EBT > 0, EBT * THUE, 0)
        CASH_FLOWS = EBT - THUE_PHAI_NOP
        
        cf_data = {
            "Năm": [0] + years,
            "Doanh thu (VND)": [0] + DOANH_THU,
            "Chi phí (VND)": [0] + CHI_PHI,
            "Lợi nhuận trước Thuế (EBT)": [0] + list(EBT),
            "Thuế (VND)": [0] + list(THUE_PHAI_NOP),
            "Dòng tiền thuần (VND)": [-VON_DAU_TU] + list(CASH_FLOWS)
        }
        
        df_cash_flow = pd.DataFrame(cf_data).set_index("Năm")
        
        st.dataframe(df_cash_flow.style.format('{:,.0f}'), use_container_width=True)
        
        # --- Chức năng 3: Tính toán các chỉ số hiệu quả ---
        st.markdown("---")
        st.subheader("3. Tính toán Các Chỉ số Đánh giá Hiệu quả Dự án 🔢")
        
        project_metrics = calculate_project_metrics(
            initial_investment=VON_DAU_TU,
            cash_flows=CASH_FLOWS,
            wacc=WACC,
            project_life=DONG_DOI
        )
        
        col_npv, col_irr, col_pp, col_dpp = st.columns(4)
        
        with col_npv:
            st.metric(
                label="Giá trị Hiện tại Ròng (NPV)", 
                value=f"{project_metrics['NPV']:,.0f} VND",
                delta="Dự án KHẢ THI" if project_metrics['NPV'] > 0 else "Dự án KHÔNG KHẢ THI"
            )
        with col_irr:
            st.metric(
                label="Tỷ suất Hoàn vốn Nội bộ (IRR)", 
                value=f"{project_metrics['IRR']*100:.2f} %",
                delta=f"WACC: {WACC*100:.2f} %"
            )
        with col_pp:
            st.metric(
                label="Thời gian Hoàn vốn (PP)", 
                value=f"{project_metrics['PP']:.2f} năm"
            )
        with col_dpp:
            st.metric(
                label="Thời gian Hoàn vốn có Chiết khấu (DPP)", 
                value=f"{project_metrics['DPP']:.2f} năm"
            )

        # --- Chức năng 4: Yêu cầu AI Phân tích ---
        st.markdown("---")
        st.subheader("4. Phân tích Chuyên sâu Chỉ số Hiệu quả (AI) 🧠")
        
        if st.button("📝 Yêu cầu AI Phân tích Chuyên sâu"):
            with st.spinner('Đang gửi dữ liệu và chờ Gemini phân tích...'):
                # Đảm bảo client đã được khởi tạo trước khi gọi hàm
                if client:
                    ai_result = get_ai_analysis_project(
                        metrics_data=project_metrics,
                        cash_flow_df=df_cash_flow.reset_index(),
                        client=client
                    )
                    st.markdown("**Kết quả Phân tích từ Gemini AI:**")
                    st.info(ai_result)
                else:
                    st.error("Không thể phân tích. Vui lòng cung cấp Khóa API Gemini hợp lệ.")

st.markdown("---")
st.info("💡 Lưu ý: Cần đảm bảo file Word cung cấp thông tin rõ ràng và nhất quán để AI trích xuất dữ liệu chính xác.")
