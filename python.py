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
