# business_plan_analyzer.py

import streamlit as st
import pandas as pd
import numpy_financial as npf
from docx import Document
from google import genai
from google.genai.errors import APIError
import json
import re

# --- Cấu hình Trang Streamlit ---
st.set_page_config(
    page_title="App Đánh Giá Phương Án Kinh Doanh 🚀",
    layout="wide"
)

st.title("Ứng dụng Đánh Giá Phương Án Kinh Doanh (PV & Dòng Tiền) 💰")
st.markdown("Tải lên file Word chứa phương án kinh doanh, AI sẽ trích xuất các chỉ số và tính toán hiệu quả dự án.")

# --- Cấu hình và Hằng số ---
FINANCIAL_METRICS = [
    "Vốn đầu tư (Initial Investment)",
    "Dòng đời dự án (Project Life)",
    "Doanh thu (Revenue)",
    "Chi phí (Cost)",
    "WACC (Weighted Average Cost of Capital)",
    "Thuế (Tax Rate)"
]

# --- Hàm gọi AI để trích xuất thông tin (Nhiệm vụ 1) ---
def extract_financial_data_from_docx(docx_content, api_key):
    """
    Sử dụng Gemini API để trích xuất các chỉ số tài chính từ nội dung văn bản.
    """
    try:
        client = genai.Client(api_key=api_key)
        model_name = 'gemini-2.5-flash'
        
        metric_list = "\n".join([f"- {m}" for m in FINANCIAL_METRICS])
        prompt = f"""
        Bạn là một chuyên gia tài chính và phân tích dữ liệu. Nhiệm vụ của bạn là đọc nội dung báo cáo kinh doanh bên dưới và trích xuất 
        chính xác các chỉ số sau:
        {metric_list}

        LƯU Ý QUAN TRỌNG:
        1. Vốn đầu tư, Doanh thu, Chi phí phải là một **giá trị số** (triệu, tỷ, hoặc đơn vị tiền tệ). Nếu chỉ đề cập đến năm đầu, hãy lấy giá trị đó.
        2. Dòng đời dự án, Thuế, WACC phải là một **giá trị số**. Dòng đời dự án là số năm. Thuế và WACC là tỷ lệ phần trăm (ví dụ: 10% trích thành 0.10).
        3. Dòng đời dự án (Project Life) là số năm dự án hoạt động. Nếu không tìm thấy, đặt là 5 năm.
        4. Doanh thu (Revenue) và Chi phí (Cost) nếu không được đề cập rõ theo năm, hãy giả định chúng là giá trị **ổn định hàng năm** (Annual) cho các năm tiếp theo.
        5. Đưa ra KẾT QUẢ CUỐI CÙNG dưới dạng một **JSON object** (chỉ có JSON, không có thêm lời giải thích hay văn bản nào khác) với cấu trúc:
        {{
            "Vốn đầu tư": [Giá trị số],
            "Dòng đời dự án": [Số năm],
            "Doanh thu": [Giá trị số hàng năm],
            "Chi phí": [Giá trị số hàng năm],
            "WACC": [Tỷ lệ chiết khấu dạng thập phân, ví dụ: 0.12],
            "Thuế": [Tỷ lệ thuế dạng thập phân, ví dụ: 0.20]
        }}

        Nội dung Phương án Kinh doanh:
        ---
        {docx_content}
        ---
        """

        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        
        # Trích xuất chuỗi JSON từ phản hồi của AI
        json_string = response.text.strip()
        if json_string.startswith("```json"):
            json_string = json_string[7:]
        if json_string.endswith("```"):
            json_string = json_string[:-3]
        
        data = json.loads(json_string)
        return data

    except APIError as e:
        st.error(f"Lỗi gọi Gemini API: Vui lòng kiểm tra Khóa API hoặc giới hạn sử dụng. Chi tiết lỗi: {e}")
        return None
    except json.JSONDecodeError:
        st.error("Lỗi phân tích cú pháp JSON từ AI. Vui lòng thử lại hoặc điều chỉnh prompt.")
        return None
    except Exception as e:
        st.error(f"Đã xảy ra lỗi không xác định trong quá trình trích xuất AI: {e}")
        return None

# --- Hàm xây dựng bảng dòng tiền (Nhiệm vụ 2) ---
def create_cash_flow_table(data):
    """Xây dựng bảng dòng tiền dự án từ dữ liệu đã lọc."""
    try:
        # Lấy các giá trị đã được chuyển đổi thành số (numeric)
        I = float(data.get("Vốn đầu tư", 0))
        N = int(data.get("Dòng đời dự án", 5)) # Giả định 5 năm nếu không trích được
        R = float(data.get("Doanh thu", 0))
        C = float(data.get("Chi phí", 0))
        T = float(data.get("Thuế", 0.20))      # Giả định 20% nếu không trích được

        # Tạo chuỗi năm cho bảng dòng tiền
        years = list(range(0, N + 1))
        
        # 1. Lợi nhuận trước thuế và lãi (EBIT)
        EBIT = [0] + [R - C] * N
        
        # 2. Thuế TNDN (Tax)
        # Sử dụng max(0, ...) để tránh thuế âm (lỗ)
        Tax = [0] + [max(0, ebit * T) for ebit in EBIT[1:]]
        
        # 3. Lợi nhuận sau thuế (EAT)
        EAT = [0] + [EBIT[i] - Tax[i] for i in range(1, N + 1)]
        
        # 4. Dòng tiền thuần hàng năm (Annual Net Cash Flow - ANCF)
        # Giả định đơn giản ANCF = EAT
        ANCF = [0] + EAT[1:] 

        # 5. Dòng tiền ròng (Net CF)
        CashFlows = [-I] + ANCF[1:]
        
        # Tạo DataFrame
        df_cf = pd.DataFrame({
            "Năm": years,
            "Doanh thu (R)": [0] + [R] * N,
            "Chi phí (C)": [0] + [C] * N,
            "Lợi nhuận trước thuế (EBIT)": EBIT,
            "Thuế (Tax)": Tax,
            "Lợi nhuận sau thuế (EAT)": EAT,
            "Dòng tiền thuần (ANCF)": ANCF,
            "Vốn đầu tư (I)": [-I if year == 0 else 0 for year in years],
            "Dòng tiền ròng (Net CF)": CashFlows
        })
        
        return df_cf, CashFlows

    except Exception as e:
        # Khối except để xử lý lỗi và ngăn SyntaxError
        st.error(f"Lỗi khi xây dựng bảng dòng tiền: {e}. Vui lòng kiểm tra dữ liệu trích xuất từ AI.")
        return None, None

# --- Hàm tính toán các chỉ số (Nhiệm vụ 3) ---
def calculate_project_metrics(cash_flows, wacc):
    """Tính toán NPV, IRR, PP, và DPP."""
    
    # 1. Net Present Value (NPV)
    npv = npf.npv(wacc, cash_flows)
    
    # 2. Internal Rate of Return (IRR)
    try:
        irr = npf.irr(cash_flows)
    except:
        irr = None 

    # 3. Payback Period (PP) và DPP (Discounted Payback Period)
    pp, dpp = None, None
    initial_investment = abs(cash_flows[0])
    
    discounted_cash_flows = [cf / (1 + wacc)**t for t, cf in enumerate(cash_flows)]
    cumulative_cf = 0
    cumulative_dcf = 0

    for t in range(1, len(cash_flows)):
        cumulative_cf += cash_flows[t]
        cumulative_dcf += discounted_cash_flows[t]
        
        # Tính PP
        if pp is None and cash_flows[t] > 0 and cumulative_cf >= initial_investment:
            prev_cf = cumulative_cf - cash_flows[t]
            pp = (t - 1) + (initial_investment - prev_cf) / cash_flows[t] 

        # Tính DPP
        if dpp is None and discounted_cash_flows[t] > 0 and cumulative_dcf >= initial_investment:
            prev_dcf = cumulative_dcf - discounted_cash_flows[t]
            dpp = (t - 1) + (initial_investment - prev_dcf) / discounted_cash_flows[t]
            
        if pp is not None and dpp is not None:
            break
            
    # Định dạng kết quả
    pp_str = f"{pp:.2f} năm" if pp is not None and pp > 0 else "Không hoàn vốn"
    dpp_str = f"{dpp:.2f} năm" if dpp is not None and dpp > 0 else "Không hoàn vốn (DCF)"
    
    return {
        "NPV (Giá trị hiện tại ròng)": npv,
        "IRR (Tỷ suất sinh lợi nội bộ)": irr,
        "PP (Thời gian hoàn vốn)": pp_str,
        "DPP (Thời gian hoàn vốn có chiết khấu)": dpp_str
    }

# --- Hàm gọi AI phân tích (Nhiệm vụ 4) ---
def get_ai_evaluation(metrics_data, wacc, api_key):
    """Gửi các chỉ số đã tính toán đến Gemini API và nhận nhận xét đánh giá."""
    try:
        client = genai.Client(api_key=api_key)
        model_name = 'gemini-2.5-flash'

        metrics_display = "\n".join([f"- {k}: {v}" for k, v in metrics_data.items()])
        
        prompt = f"""
        Bạn là một Chuyên gia Thẩm định Dự án đầu tư chuyên nghiệp. Dựa trên các chỉ số hiệu quả dự án sau và Tỷ suất chiết khấu (WACC), 
        hãy đưa ra nhận xét, kết luận (khoảng 3-5 đoạn) về tính khả thi và hiệu quả tài chính của dự án. 

        Tiêu chí đánh giá:
        1. NPV: Cần phải > 0.
        2. IRR: Cần phải > WACC.
        3. PP/DPP: Cần phải nhỏ hơn Dòng đời dự án.

        Dữ liệu và Chỉ số:
        - Tỷ suất Chiết khấu (WACC): {wacc:.2%}
        - {metrics_display}

        Nhận xét và Kết luận (Bằng tiếng Việt):
        """

        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        return response.text

    except APIError as e:
        return f"Lỗi gọi Gemini API: Vui lòng kiểm tra Khóa API hoặc giới hạn sử dụng. Chi tiết lỗi: {e}"
    except Exception as e:
        return f"Đã xảy ra lỗi không xác định: {e}"

# =========================================================================
# --- Logic Ứng dụng Streamlit ---
# =========================================================================

# 1. Tải file Word
uploaded_file = st.file_uploader(
    "1. Tải file Word (.docx) chứa Phương án Kinh doanh:",
    type=['docx']
)

if uploaded_file is not None:
    document = Document(uploaded_file)
    docx_content = "\n".join([para.text for para in document.paragraphs])
        
    st.info("File đã tải lên thành công. Nhấn nút bên dưới để trích xuất dữ liệu.")

    if st.button("Trích xuất Dữ liệu Tài chính (AI) 🤖"):
        api_key = st.secrets.get("GEMINI_API_KEY")
        
        if not api_key:
            st.error("Lỗi: Không tìm thấy Khóa API. Vui lòng cấu hình Khóa 'GEMINI_API_KEY' trong Streamlit Secrets.")
        else:
            with st.spinner('Đang gửi nội dung file Word đến Gemini để trích xuất...'):
                financial_data = extract_financial_data_from_docx(docx_content, api_key)

            if financial_data:
                st.session_state['financial_data'] = financial_data
                st.success("Trích xuất dữ liệu thành công!")
                
                # --- Nhiệm vụ 1: Hiển thị Dữ liệu đã trích xuất ---
                st.subheader("1. Dữ liệu Tài chính đã Trích xuất")
                extracted_df = pd.DataFrame(financial_data.items(), columns=["Chỉ tiêu", "Giá trị"])
                
                extracted_df['Giá trị hiển thị'] = extracted_df.apply(
                    lambda row: f"{row['Giá trị']:,}" if row['Chỉ tiêu'] not in ["WACC", "Thuế", "Dòng đời dự án"] 
                                else (f"{row['Giá trị']:.2%}" if row['Chỉ tiêu'] in ["WACC", "Thuế"] else row['Giá trị']), 
                    axis=1
                )
                st.dataframe(extracted_df[['Chỉ tiêu', 'Giá trị hiển thị']], use_container_width=True, hide_index=True)
                
                # Xây dựng bảng dòng tiền
                df_cf, cash_flows = create_cash_flow_table(financial_data)
                
                if df_cf is not None and cash_flows is not None:
                    st.session_state['df_cf'] = df_cf
                    st.session_state['cash_flows'] = cash_flows
                    
                    # --- Nhiệm vụ 2: Hiển thị Bảng Dòng Tiền ---
                    st.divider()
                    st.subheader("2. Bảng Dòng tiền Dự án (Net Cash Flow)")
                    st.dataframe(df_cf.style.format({
                        col: '{:,.0f}' for col in df_cf.columns if col not in ['Năm']
                    }), use_container_width=True, hide_index=True)
                    
                    # --- Nhiệm vụ 3: Tính toán và Hiển thị Chỉ số Đánh giá ---
                    wacc = financial_data.get("WACC", 0.12)
                    project_metrics = calculate_project_metrics(cash_flows, wacc)
                    st.session_state['project_metrics'] = project_metrics
                    
                    st.divider()
                    st.subheader("3. Các Chỉ số Đánh giá Hiệu quả Dự án")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        npv_value = project_metrics["NPV (Giá trị hiện tại ròng)"]
                        st.metric(
                            label="Giá trị hiện tại ròng (NPV)",
                            value=f"{npv_value:,.0f}",
                            delta="Dự án KHẢ THI" if npv_value > 0 else "Dự án KHÔNG KHẢ THI",
                            delta_color="normal" if npv_value > 0 else "inverse"
                        )
                    with col2:
                        irr_value = project_metrics["IRR (Tỷ suất sinh lợi nội bộ)"]
                        if irr_value is not None:
                             st.metric(
                                label=f"Tỷ suất sinh lợi nội bộ (IRR) (WACC: {wacc:.2%})",
                                value=f"{irr_value:.2%}",
                                delta="IRR > WACC" if irr_value > wacc else "IRR < WACC",
                                delta_color="normal" if irr_value > wacc else "inverse"
                            )
                        else:
                             st.metric(label=f"Tỷ suất sinh lợi nội bộ (IRR) (WACC: {wacc:.2%})", value="N/A")
                        
                    with col3:
                        st.metric(
                            label="Thời gian hoàn vốn (PP)",
                            value=project_metrics["PP (Thời gian hoàn vốn)"]
                        )
                    with col4:
                        st.metric(
                            label="Thời gian hoàn vốn có chiết khấu (DPP)",
                            value=project_metrics["DPP (Thời gian hoàn vốn có chiết khấu)"]
                        )

# --- Nhiệm vụ 4: Phân tích AI (Chạy sau khi đã tính toán) ---
if 'project_metrics' in st.session_state and 'financial_data' in st.session_state:
    st.divider()
    st.subheader("4. Nhận xét Đánh giá Hiệu quả Dự án (AI)")

    if st.button("Yêu cầu AI Phân tích Chỉ số 🧠"):
        api_key = st.secrets.get("GEMINI_API_KEY")
        wacc = st.session_state['financial_data'].get("WACC", 0.12)

        if api_key:
            with st.spinner('Đang gửi dữ liệu và chờ Gemini phân tích...'):
                ai_result = get_ai_evaluation(st.session_state['project_metrics'], wacc, api_key)
                st.markdown("**Kết quả Phân tích từ Gemini AI:**")
                st.info(ai_result)
        else:
            st.error("Lỗi: Không tìm thấy Khóa API. Vui lòng cấu hình Khóa 'GEMINI_API_KEY' trong Streamlit Secrets.")

elif uploaded_file is None:
    st.markdown("---")
    st.warning("Vui lòng tải lên file Word và thực hiện bước **Trích xuất Dữ liệu Tài chính (AI)** để bắt đầu.")
