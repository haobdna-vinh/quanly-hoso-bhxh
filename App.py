import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import io
import base64
import barcode
from barcode.writer import ImageWriter

# ==========================================
# 1. CẤU HÌNH TRANG WEB STREAMLIT
# ==========================================
st.set_page_config(
    page_title="BHXH Nghệ An - Quản lý hồ sơ B5",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS cho giao diện phong bì và tiêu đề
st.markdown("""
<style>
    .app-header {
        background-color: #0066cc;
        color: white;
        padding: 12px 20px;
        border-radius: 5px;
        font-size: 18px;
        font-weight: bold;
        margin-bottom: 20px;
    }
    .envelope-box {
        border: 2px solid #000;
        padding: 25px;
        background-color: #ffffff;
        font-family: Arial, sans-serif;
        color: #000;
        width: 100%;
        max-width: 800px;
        margin: 0 auto;
        box-sizing: border-box;
    }
    .border-notice {
        border: 1.5px solid #000;
        padding: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 13px;
    }
    @media print {
        .stApp > header, footer, .sidebar, .stButton {
            display: none !important;
        }
        .envelope-box {
            border: 1px solid #000 !important;
            width: 100% !important;
        }
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="app-header">Bảo hiểm xã hội tỉnh Nghệ An — Quản lý chuyển phát và thu hồi Mẫu 05 chuẩn B5</div>', unsafe_allow_html=True)

# ==========================================
# 2. HÀM TẠO MÃ VẠCH CODE128 CHO MÁY QUÉT
# ==========================================
def get_barcode_image_base64(code_text: str) -> str:
    """
    Tự động chuẩn hóa mã bưu gửi thành CHỮ IN HOA và tạo ảnh mã vạch Code128 dạng Base64
    để nhúng trực tiếp vào phong bì HTML in ấn.
    """
    code_clean = str(code_text).strip().upper()
    if not code_clean:
        return ""
    
    try:
        code128 = barcode.get_barcode_class('code128')
        rv = io.BytesIO()
        writer_options = {
            'write_text': False,
            'module_height': 12.0,
            'module_width': 0.35,
            'quiet_zone': 2.0
        }
        code128(code_clean, writer=ImageWriter()).write(rv, options=writer_options)
        b64_str = base64.b64encode(rv.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{b64_str}"
    except Exception as e:
        st.error(f"Lỗi tạo mã vạch: {e}")
        return ""

# ==========================================
# 3. KẾT NỐI CƠ SỞ DỮ LIỆU POSTGRESQL (SUPABASE)
# ==========================================
@st.cache_resource
def init_connection():
    return psycopg2.connect(
        host=st.secrets["postgres"]["host"],
        port=st.secrets["postgres"]["port"],
        database=st.secrets["postgres"]["database"],
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"],
        sslmode="require",  # Bắt buộc có cho Supabase Cloud
        connect_timeout=10
    )

def get_db_connection():
    try:
        conn = init_connection()
        return conn
    except Exception:
        # Tự động kết nối lại nếu cache bị hết hạn
        st.cache_resource.clear()
        return init_connection()

def load_hoso_data():
    try:
        conn = get_db_connection()
        query = "SELECT * FROM quanly_hoso ORDER BY id DESC;"
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        st.error(f"Lỗi tải dữ liệu từ CSDL: {e}")
        return pd.DataFrame()

# DANH SÁCH 15 LOẠI HỒ SƠ BHXH CHUẨN HÓA
DANH_SACH_LOAI_HO_SO = [
    "Sổ chốt BHXH (Hồ sơ BHXH)",
    "Thẻ BHYT",
    "Quyết định hưởng chế độ BHXH 1 lần",
    "Quyết định hưởng chế độ Hưu trí",
    "Quyết định hưởng chế độ Tử tuất",
    "Quyết định hưởng chế độ Ốm đau, Thai sản",
    "Quyết định hưởng chế độ Tai nạn lao động, Bệnh nghề nghiệp",
    "Quyết định hưởng trợ cấp Thất nghiệp",
    "Tờ khai tham gia, điều chỉnh thông tin BHXH, BHYT (Mẫu TK1-TS)",
    "Danh sách lao động tham gia BHXH, BHYT (Mẫu D02-LT)",
    "Thông báo kết quả đóng BHXH, BHYT, BHTN (Mẫu C12-TS)",
    "Biên bản điều tra Tai nạn lao động",
    "Hồ sơ cấp lại sổ BHXH / thẻ BHYT",
    "Hồ sơ điều chỉnh thông tin nhân thân",
    "Hồ sơ chuyển nơi hưởng trợ cấp thất nghiệp"
]

# ==========================================
# 4. GIAO DIỆN CHÍNH (TABS)
# ==========================================
tab1, tab2, tab3 = st.tabs(["📝 Nhập / In Hồ Sơ B5", "📊 Quản Lý Hồ Sơ", "⚙️ Cấu Hình System"])

# ------------------------------------------
# TAB 1: NHẬP VÀ IN HỒ SƠ
# ------------------------------------------
with tab1:
    st.subheader("Nhập thông tin bưu gửi & Tạo phôi in Mẫu 05")
    
    col_input, col_preview = st.columns([1, 1.2])
    
    with col_input:
        with st.form("form_nhap_hoso", clear_on_submit=False):
            # Ngày nhận mặc định lùi lại 1 ngày so với hiện tại
            default_ngay_nhan = datetime.now().date() - timedelta(days=1)
            ngay_nhan = st.date_input("Ngày nhận hồ sơ:", value=default_ngay_nhan)
            
            ma_van_don_raw = st.text_input("Mã vận đơn bưu điện:", value="cd468359126vn")
            # Tự động viết hoa toàn bộ mã vận đơn
            ma_van_don = ma_van_don_raw.strip().upper()
            
            ten_don_vi = st.text_input("Kính gửi (Tên đơn vị/Công ty):", "CÔNG TY CP XÂY DỰNG & TM 648")
            ma_don_vi = st.text_input("Mã đơn vị:", "TA0396A")
            dia_chi = st.text_area("Địa chỉ:", "Số 65 Nguyễn Đình Chiểu, , Na (Lê Lợi), Phường Thành Vinh, Tỉnh Nghệ An")
            dien_thoai = st.text_input("Điện thoại:", "0917.886.909/0915080710")
            
            loai_ho_so = st.selectbox("Nội dung gửi (Loại hồ sơ):", DANH_SACH_LOAI_HO_SO)
            so_ban_ke = st.text_input("Số bản kê 05:", "111")
            
            btn_save = st.form_submit_button("💾 Lưu Dữ Liệu & Cập Nhật Phôi In", type="primary")
            
            if btn_save:
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    insert_query = """
                        INSERT INTO quanly_hoso (ngay_nhan, ma_van_don, ten_don_vi, ma_don_vi, dia_chi, dien_thoai, noi_dung_gui, so_ban_ke)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    cursor.execute(insert_query, (ngay_nhan, ma_van_don, ten_don_vi, ma_don_vi, dia_chi, dien_thoai, loai_ho_so, so_ban_ke))
                    conn.commit()
                    cursor.close()
                    st.success(f"✅ Đã lưu hồ sơ mã vận đơn {ma_van_don} thành công!")
                except Exception as e:
                    st.error(f"Lỗi khi lưu vào CSDL: {e}")

    with col_preview:
        st.write("**Xem trước phôi in phong bì B5:**")
        
        # Sinh ảnh mã vạch Base64 từ mã vận đơn chữ in hoa
        barcode_b64 = get_barcode_image_base64(ma_van_don)
        
        # Tạo khung phong bì xem trước
        envelope_html = f"""
        <div class="envelope-box">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="width: 55%; vertical-align: top; font-size: 13px;">
                        <b>NGƯỜI GỬI: BHXH TỈNH NGHỆ AN</b><br>
                        Địa chỉ: Số 06, đường Trường Thi, TP Vinh, Nghệ An<br>
                        Điện thoại: 0238.3844888
                    </td>
                    <td style="width: 45%; text-align: center; vertical-align: top;">
                        <div style="font-size: 13px; font-weight: bold; margin-bottom: 3px;">
                            Mã vận đơn bưu điện:
                        </div>
                        {f'<img src="{barcode_b64}" style="max-height: 55px; width: 210px; object-fit: contain; display: block; margin: 0 auto;" />' if barcode_b64 else ''}
                        <div style="font-size: 15px; font-weight: bold; letter-spacing: 1.5px; margin-top: 2px;">
                            {ma_van_don}
                        </div>
                    </td>
                </tr>
            </table>
            
            <table style="width: 100%; margin-top: 20px; border-collapse: collapse;">
                <tr>
                    <td style="width: 40%; vertical-align: middle;">
                        <div class="border-notice">
                            PHÁT ĐỒNG KIỂM, THU HỒI<br>"MẪU 05" TRONG PHONG BÌ
                        </div>
                    </td>
                    <td style="width: 60%; padding-left: 20px; vertical-align: top; font-size: 14px; line-height: 1.5;">
                        <b>Kính gửi:</b> <span style="font-size: 15px; font-weight: bold;">{ten_don_vi}</span><br>
                        <b>Mã đơn vị:</b> {ma_don_vi}<br>
                        <b>Địa chỉ:</b> {dia_chi}<br>
                        <b>Điện thoại:</b> {dien_thoai}<br>
                        <b>Nội dung gửi:</b> {loai_ho_so}<br>
                        <b>Số bản kê 05:</b> {so_ban_ke}
                    </td>
                </tr>
            </table>
        </div>
        """
        st.markdown(envelope_html, unsafe_allow_html=True)

# ------------------------------------------
# TAB 2: QUẢN LÝ DỮ LIỆU HỒ SƠ
# ------------------------------------------
with tab2:
    st.subheader("Danh sách hồ sơ đã nhận & gửi")
    if st.button("🔄 Tải lại dữ liệu"):
        st.cache_resource.clear()
        
    df_data = load_hoso_data()
    if not df_data.empty:
        st.dataframe(df_data, use_container_width=True)
        
        # Xuất dữ liệu ra Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_data.to_excel(writer, index=False, sheet_name='Danh_Sach_Ho_So')
            
        st.download_button(
            label="📥 Tải về danh sách Excel",
            data=buffer.getvalue(),
            file_name=f"DS_Ho_So_BHXH_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Chưa có dữ liệu hồ sơ nào trong CSDL.")

# ------------------------------------------
# TAB 3: CẤU HÌNH HỆ THỐNG
# ------------------------------------------
with tab3:
    st.subheader("Trạng thái kết nối CSDL Supabase")
    try:
        conn = get_db_connection()
        st.success("✅ Kết nối đến CSDL PostgreSQL Supabase thành công!")
    except Exception as e:
        st.error(f"❌ Kết nối CSDL thất bại: {e}")