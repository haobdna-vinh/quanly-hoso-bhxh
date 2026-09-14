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

# Custom CSS cho phong bì B5 và giao diện
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
        margin: 10px auto;
        box-sizing: border-box;
    }
    .border-notice {
        border: 1.5px solid #000;
        padding: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 13px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="app-header">Bảo hiểm xã hội tỉnh Nghệ An — Quản lý chuyển phát và thu hồi Mẫu 05 chuẩn B5</div>', unsafe_allow_html=True)

# ==========================================
# 2. HÀM TẠO MÃ VẠCH CODE128
# ==========================================
def get_barcode_image_base64(code_text: str) -> str:
    """Tự động viết hoa mã bưu gửi và tạo ảnh mã vạch Code128 dạng Base64"""
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
    except Exception:
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
        sslmode="require",
        connect_timeout=10
    )

def get_db_connection():
    try:
        return init_connection()
    except Exception:
        st.cache_resource.clear()
        return init_connection()

def load_hoso_data():
    try:
        conn = get_db_connection()
        query = "SELECT * FROM quanly_hoso ORDER BY id DESC;"
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        st.error(f"Lỗi tải dữ liệu: {e}")
        return pd.DataFrame()

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
# 4. GIAO DIỆN CHÍNH DẠNG 3 TAB CHUẨN
# ==========================================
tab1, tab2, tab3 = st.tabs([
    "📥 Tab 1: Nhập danh sách hồ sơ gửi",
    "🔍 Tab 2: Tra cứu hồ sơ & In phong bì",
    "🔄 Tab 3: Theo dõi thu hồi biên bản mẫu 05"
])

# ------------------------------------------
# TAB 1: NHẬP DANH SÁCH HỒ SƠ GỬI
# ------------------------------------------
with tab1:
    st.subheader("Nhập thông tin bưu gửi hồ sơ BHXH mới")
    
    with st.form("form_nhap_hoso", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            default_ngay_nhan = datetime.now().date() - timedelta(days=1)
            ngay_nhan = st.date_input("Ngày nhận hồ sơ:", value=default_ngay_nhan)
            ma_van_don_raw = st.text_input("Mã vận đơn bưu điện:", placeholder="Nhập mã vạch bưu gửi (ví dụ: CD468359126VN)...")
            ten_don_vi = st.text_input("Kính gửi (Tên đơn vị/Công ty):", placeholder="Tên đơn vị sử dụng lao động...")
            ma_don_vi = st.text_input("Mã đơn vị:", placeholder="Ví dụ: TA0396A")
            
        with col2:
            dia_chi = st.text_area("Địa chỉ:", placeholder="Địa chỉ nhận thư...", height=108)
            dien_thoai = st.text_input("Điện thoại:", placeholder="Số điện thoại người nhận...")
            loai_ho_so = st.selectbox("Nội dung gửi (Loại hồ sơ):", DANH_SACH_LOAI_HO_SO)
            so_ban_ke = st.text_input("Số bản kê 05:", value="111")
            
        btn_submit = st.form_submit_button("💾 Lưu Thông Tin Hồ Sơ", type="primary", use_container_width=True)
        
        if btn_submit:
            ma_van_don = ma_van_don_raw.strip().upper()
            if not ma_van_don or not ten_don_vi:
                st.warning("⚠️ Vui lòng điền đầy đủ Mã vận đơn và Tên đơn vị!")
            else:
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    insert_query = """
                        INSERT INTO quanly_hoso 
                        (ngay_nhan, ma_van_don, ten_don_vi, ma_don_vi, dia_chi, dien_thoai, noi_dung_gui, so_ban_ke, trang_thai_m05)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    cursor.execute(insert_query, (
                        ngay_nhan, ma_van_don, ten_don_vi, ma_don_vi, 
                        dia_chi, dien_thoai, loai_ho_so, so_ban_ke, "Chưa thu hồi"
                    ))
                    conn.commit()
                    cursor.close()
                    st.success(f"✅ Đã lưu thành công hồ sơ bưu gửi {ma_van_don}!")
                except Exception as e:
                    st.error(f"❌ Lỗi khi lưu dữ liệu: {e}")

# ------------------------------------------
# TAB 2: TRA CỨU HỒ SƠ & IN PHONG BÌ
# ------------------------------------------
with tab2:
    st.subheader("Tra cứu thông tin & In phôi phong bì B5")
    
    df_all = load_hoso_data()
    
    if not df_all.empty:
        search_term = st.text_input("🔍 Tìm kiếm theo Mã vận đơn, Mã đơn vị hoặc Tên đơn vị:", "")
        
        if search_term:
            df_filtered = df_all[
                df_all['ma_van_don'].str.contains(search_term, case=False, na=False) |
                df_all['ten_don_vi'].str.contains(search_term, case=False, na=False) |
                df_all['ma_don_vi'].str.contains(search_term, case=False, na=False)
            ]
        else:
            df_filtered = df_all
            
        st.dataframe(df_filtered, use_container_width=True)
        
        st.divider()
        st.subheader("🖨️ Chọn hồ sơ để tạo phôi in phong bì B5")
        
        selected_code = st.selectbox(
            "Chọn Mã vận đơn cần in phong bì:", 
            options=df_filtered['ma_van_don'].tolist() if not df_filtered.empty else []
        )
        
        if selected_code:
            row = df_filtered[df_filtered['ma_van_don'] == selected_code].iloc[0]
            
            ma_van_don_hoa = str(row['ma_van_don']).upper()
            barcode_b64 = get_barcode_image_base64(ma_van_don_hoa)
            
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
                                {ma_van_don_hoa}
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
                            <b>Kính gửi:</b> <span style="font-size: 15px; font-weight: bold;">{row['ten_don_vi']}</span><br>
                            <b>Mã đơn vị:</b> {row['ma_don_vi']}<br>
                            <b>Địa chỉ:</b> {row['dia_chi']}<br>
                            <b>Điện thoại:</b> {row['dien_thoai']}<br>
                            <b>Nội dung gửi:</b> {row['noi_dung_gui']}<br>
                            <b>Số bản kê 05:</b> {row['so_ban_ke']}
                        </td>
                    </tr>
                </table>
            </div>
            """
            st.markdown(envelope_html, unsafe_allow_html=True)
    else:
        st.info("Chưa có hồ sơ nào trong CSDL để tra cứu.")

# ------------------------------------------
# TAB 3: THEO DÕI THU HỒI BIÊN BẢN MẪU 05
# ------------------------------------------
with tab3:
    st.subheader("Theo dõi & Cập nhật trạng thái thu hồi Biên bản Mẫu 05")
    
    df_all = load_hoso_data()
    
    if not df_all.empty:
        # Tổng quan thống kê
        chua_thu_hoi = len(df_all[df_all.get('trang_thai_m05', '') != 'Đã thu hồi'])
        da_thu_hoi = len(df_all[df_all.get('trang_thai_m05', '') == 'Đã thu hồi'])
        
        col_st1, col_st2, col_st3 = st.columns(3)
        col_st1.metric("Tổng số hồ sơ gửi", len(df_all))
        col_st2.metric("Chưa thu hồi Mẫu 05", chua_thu_hoi)
        col_st3.metric("Đã thu hồi Mẫu 05", da_thu_hoi)
        
        st.divider()
        st.write("**Cập nhật nhanh trạng thái thu hồi:**")
        
        with st.form("form_update_m05"):
            col_m1, col_m2 = st.columns([2, 1])
            with col_m1:
                selected_mvd = st.selectbox("Chọn Mã vận đơn cập nhật:", df_all['ma_van_don'].tolist())
            with col_m2:
                trang_thai_moi = st.selectbox("Trạng thái Mẫu 05:", ["Đã thu hồi", "Chưa thu hồi"])
                
            btn_update = st.form_submit_button("🔄 Cập Nhật Trạng Thái", type="primary")
            
            if btn_update:
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    update_query = "UPDATE quanly_hoso SET trang_thai_m05 = %s WHERE ma_van_don = %s;"
                    cursor.execute(update_query, (trang_thai_moi, selected_mvd))
                    conn.commit()
                    cursor.close()
                    st.success(f"✅ Đã cập nhật trạng thái '{trang_thai_moi}' cho mã vận đơn {selected_mvd}!")
                    st.cache_resource.clear()
                except Exception as e:
                    st.error(f"Lỗi cập nhật CSDL: {e}")
                    
        st.write("**Bảng danh sách chi tiết Mẫu 05:**")
        st.dataframe(df_all, use_container_width=True)
    else:
        st.info("Chưa có dữ liệu để theo dõi Mẫu 05.")