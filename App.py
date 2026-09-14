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
    initial_sidebar_state="collapsed"
)

# Custom CSS cho phong bì B5 ngang (235mm x 165mm) và Print CSS
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
    
    /* Khung phong bì B5 Ngang tiêu chuẩn trên web (Tỷ lệ 235mm x 165mm) */
    .b5-envelope {
        position: relative;
        width: 235mm;
        height: 165mm;
        background-color: #ffffff;
        border: 2px solid #000;
        margin: 15px auto;
        box-sizing: border-box;
        font-family: Arial, sans-serif;
        color: #000;
        page-break-after: always;
        overflow: hidden;
    }
    
    /* Căn chỉnh vị trí tuyệt đối theo mm */
    .sender-info {
        position: absolute;
        left: 10mm;
        top: 35mm;
        font-size: 13px;
        line-height: 1.4;
    }
    
    .notice-box {
        position: absolute;
        left: 10mm;
        top: 65mm;
        width: 65mm;
        height: 20mm;
        border: 1.5px solid #000;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        font-weight: bold;
        font-size: 12px;
        line-height: 1.3;
        padding: 2mm;
        box-sizing: border-box;
    }
    
    .barcode-area {
        position: absolute;
        left: 110mm;
        top: 60mm;
        text-align: center;
    }
    
    .receiver-info {
        position: absolute;
        left: 100mm;
        top: 95mm;
        font-size: 14px;
        line-height: 1.6;
        right: 10mm;
    }
    
    /* CSS hỗ trợ in hàng loạt */
    @media print {
        body * {
            visibility: hidden;
        }
        .print-area, .print-area * {
            visibility: visible;
        }
        .print-area {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
        }
        .b5-envelope {
            border: 1px solid #000 !important;
            margin: 0 !important;
            page-break-after: always !important;
        }
        .stApp > header, footer, .sidebar, .stButton, .no-print {
            display: none !important;
        }
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="app-header no-print">Bảo hiểm xã hội tỉnh Nghệ An — Quản lý chuyển phát và thu hồi Mẫu 05 chuẩn B5</div>', unsafe_allow_html=True)

# ==========================================
# 2. HÀM TẠO MÃ VẠCH CODE128
# ==========================================
def get_barcode_image_base64(code_text: str) -> str:
    """Tự động chuẩn hóa mã bưu gửi thành CHỮ IN HOA và tạo ảnh mã vạch Code128 dạng Base64"""
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
# 3. KẾT NỐI VÀ THAO TÁC CƠ SỞ DỮ LIỆU
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

def load_dm_donvi():
    """Tải danh mục đơn vị"""
    try:
        conn = get_db_connection()
        query = "SELECT ma_don_vi, ten_don_vi, dia_chi, dien_thoai FROM dm_donvi ORDER BY ma_don_vi;"
        return pd.read_sql_query(query, conn)
    except Exception:
        return pd.DataFrame(columns=["ma_don_vi", "ten_don_vi", "dia_chi", "dien_thoai"])

def upsert_dm_donvi(ma_dv, ten_dv, dia_chi, dien_thoai):
    """Thêm mới hoặc cập nhật thông tin đơn vị vào DM_donvi"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO dm_donvi (ma_don_vi, ten_don_vi, dia_chi, dien_thoai)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (ma_don_vi) 
            DO UPDATE SET 
                ten_don_vi = EXCLUDED.ten_don_vi,
                dia_chi = EXCLUDED.dia_chi,
                dien_thoai = EXCLUDED.dien_thoai;
        """
        cursor.execute(query, (ma_dv, ten_dv, dia_chi, dien_thoai))
        conn.commit()
        cursor.close()
    except Exception as e:
        st.error(f"Lỗi cập nhật DM_donvi: {e}")

def load_hoso_data(from_date=None, to_date=None, search_term=""):
    """Tải danh sách hồ sơ có lọc theo ngày và từ khóa"""
    try:
        conn = get_db_connection()
        query = "SELECT * FROM quanly_hoso WHERE 1=1"
        params = []
        
        if from_date:
            query += " AND ngay_nhan >= %s"
            params.append(from_date)
        if to_date:
            query += " AND ngay_nhan <= %s"
            params.append(to_date)
        if search_term:
            query += " AND (ma_van_don ILIKE %s OR ten_don_vi ILIKE %s OR ma_don_vi ILIKE %s)"
            pattern = f"%{search_term}%"
            params.extend([pattern, pattern, pattern])
            
        query += " ORDER BY id DESC;"
        df = pd.read_sql_query(query, conn, params=params)
        return df
    except Exception as e:
        st.error(f"Lỗi tải hồ sơ: {e}")
        return pd.DataFrame()

# DANH SÁCH LOẠI HỒ SƠ YÊU CẦU
DANH_SACH_LOAI_HO_SO = [
    "Sổ chốt BHXH", "Thẻ BHYT", "Hưu trí", "Trợ cấp tai nạn lao động", 
    "Chốt hưu", "Chế độ dưỡng sức", "Chế độ ốm đau", "Chế độ thai sản", 
    "Chế độ tuất", "Điều chỉnh thông tin người lao động", "Bảo hiểm thất nghiệp", 
    "Quyết định hưởng 1 lần", "Tăng lao động", "Giảm lao động", "Loại khác"
]

# ==========================================
# 4. GIAO DIỆN CHÍNH 3 TAB
# ==========================================
tab1, tab2, tab3 = st.tabs([
    "📥 Tab 1: Nhập hồ sơ & Cập nhật đơn vị",
    "📊 Tab 2: Thống kê & In phong bì A5/B5",
    "🔄 Tab 3: Theo dõi & Thu hồi biên bản (Mẫu 05)"
])

# ------------------------------------------
# TAB 1: NHẬP HỒ SƠ & CẬP NHẬT ĐƠN VỊ
# ------------------------------------------
with tab1:
    st.subheader("Nhập hồ sơ mới & Tự động Upsert Danh mục Đơn vị")
    
    df_dm = load_dm_donvi()
    
    # Gợi ý tìm kiếm autocomplete đơn vị
    search_dv = st.text_input("🔍 Gõ Mã hoặc Tên đơn vị để tìm kiếm nhanh (Tự động lọc):", key="search_dv_tab1")
    
    selected_unit = None
    if search_dv:
        filtered_dm = df_dm[
            df_dm['ma_don_vi'].astype(str).str.contains(search_dv, case=False, na=False) |
            df_dm['ten_don_vi'].astype(str).str.contains(search_dv, case=False, na=False)
        ]
        if not filtered_dm.empty:
            options = [f"{row['ma_don_vi']} - {row['ten_don_vi']}" for _, row in filtered_dm.iterrows()]
            selected_option = st.selectbox("Chọn đơn vị từ danh sách gợi ý:", options=options)
            sel_code = selected_option.split(" - ")[0]
            selected_unit = filtered_dm[filtered_dm['ma_don_vi'] == sel_code].iloc[0]
        else:
            st.info("💡 Không tìm thấy đơn vị khớp, thông tin bạn nhập sẽ được tự động THÊM MỚI vào CSDL.")

    # Form nhập liệu
    with st.form("form_tab1", clear_on_submit=False):
        col_left, col_right = st.columns(2)
        
        default_ngay_nhan = datetime.now().date() - timedelta(days=1)
        
        # Cho phép chỉnh sửa toàn bộ các trường để đồng bộ Upsert
        with col_left:
            ngay_nhan = st.date_input("Ngày nhận hồ sơ (mặc định lùi 1 ngày):", value=default_ngay_nhan)
            ma_van_don_raw = st.text_input("Số hiệu bưu gửi / Mã vận đơn (Cho phép quét mã vạch):")
            ma_don_vi = st.text_input("Mã đơn vị:", value=selected_unit['ma_don_vi'] if selected_unit is not None else "")
            ten_don_vi = st.text_input("Tên đơn vị:", value=selected_unit['ten_don_vi'] if selected_unit is not None else "")
            
        with col_right:
            dia_chi = st.text_area("Địa chỉ:", value=selected_unit['dia_chi'] if selected_unit is not None else "", height=108)
            dien_thoai = st.text_input("Điện thoại:", value=selected_unit['dien_thoai'] if selected_unit is not None else "")
            loai_ho_so = st.selectbox("Loại hồ sơ:", DANH_SACH_LOAI_HO_SO)
            so_ban_ke = st.text_input("Số bản kê 05:", value="111")
            
        btn_save_tab1 = st.form_submit_button("💾 Lưu Hồ Sơ & Cập Nhật Danh Mục Đơn Vị", type="primary", use_container_width=True)
        
        if btn_save_tab1:
            ma_van_don = ma_van_don_raw.strip().upper()
            if not ma_van_don or not ma_don_vi or not ten_don_vi:
                st.warning("⚠️ Vui lòng nhập đầy đủ Mã vận đơn, Mã đơn vị và Tên đơn vị!")
            else:
                try:
                    # 1. Upsert DM_donvi
                    upsert_dm_donvi(ma_don_vi, ten_don_vi, dia_chi, dien_thoai)
                    
                    # 2. Thêm vào hồ sơ
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
                    st.success(f"✅ Đã lưu hồ sơ {ma_van_don} và tự động cập nhật danh mục đơn vị {ma_don_vi} thành công!")
                except Exception as e:
                    st.error(f"❌ Lỗi khi lưu dữ liệu: {e}")

    # Bảng danh sách kết quả tìm kiếm với các nút lệnh Sửa/Xóa/In phong bì
    st.divider()
    st.subheader("Danh sách hồ sơ mới nhập / tìm kiếm")
    
    df_hoso_tab1 = load_hoso_data()
    if not df_hoso_tab1.empty:
        # Lọc danh sách cột hiển thị theo đúng yêu cầu
        display_df = df_hoso_tab1[['ma_don_vi', 'ten_don_vi', 'dia_chi', 'ma_van_don', 'ngay_nhan', 'noi_dung_gui']].copy()
        display_df.insert(0, 'STT', range(1, len(display_df) + 1))
        
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("Chưa có dữ liệu hồ sơ.")

# ------------------------------------------
# TAB 2: THỐNG KÊ & IN PHONG BÌ A5/B5
# ------------------------------------------
with tab2:
    st.subheader("Thống kê hồ sơ & In phong bì B5 ngang (235mm x 165mm) hàng loạt")
    
    # Lọc theo khoảng thời gian
    col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
    with col_f1:
        from_date = st.date_input("Từ ngày:", value=datetime.now().date() - timedelta(days=30))
    with col_f2:
        to_date = st.date_input("Đến ngày:", value=datetime.now().date())
    with col_f3:
        search_keyword = st.text_input("Từ khóa (Mã vận đơn, Tên/Mã đơn vị):", "")
        
    df_tab2 = load_hoso_data(from_date=from_date, to_date=to_date, search_term=search_keyword)
    
    if not df_tab2.empty:
        # Checkbox chọn tất cả
        select_all = st.checkbox("Select All / Chọn tất cả hồ sơ trong danh sách")
        
        # Thêm cột Checkbox chọn từng dòng
        df_tab2.insert(0, "Chon", select_all)
        
        edited_df = st.data_editor(
            df_tab2,
            column_config={"Chon": st.column_config.CheckboxColumn("Chọn in", default=False)},
            disabled=[col for col in df_tab2.columns if col != "Chon"],
            use_container_width=True,
            key="editor_tab2"
        )
        
        selected_rows = edited_df[edited_df["Chon"] == True]
        
        col_act1, col_act2 = st.columns(2)
        
        # 1. Xuất Excel hàng loạt
        with col_act1:
            if not selected_rows.empty:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    selected_rows.drop(columns=["Chon"]).to_excel(writer, index=False, sheet_name='Danh_Sach_In')
                st.download_button(
                    label=f"📥 Xuất Excel hàng loạt ({len(selected_rows)} hồ sơ đã chọn)",
                    data=buffer.getvalue(),
                    file_name=f"DS_Ho_So_BHXH_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.info("Hãy tích chọn ít nhất 1 hồ sơ để xuất Excel.")

        # 2. In hàng loạt phong bì B5 ngang (235mm x 165mm)
        with col_act2:
            show_print_view = st.button(f"🖨️ Tạo phôi in B5 hàng loạt ({len(selected_rows)} hồ sơ)", type="primary", use_container_width=True)
            
        if show_print_view and not selected_rows.empty:
            st.write("---")
            st.info("💡 **Hướng dẫn in:** Bấm nút **Ctrl + P** (hoặc Cmd + P) trên bàn phím. Tại mục máy in, chọn khổ giấy **B5/A5 ngang**, lề chọn **None (Khuyết)**.")
            
            # Render danh sách phong bì B5
            html_print_all = '<div class="print-area">'
            
            for _, row in selected_rows.iterrows():
                mvd_hoa = str(row['ma_van_don']).upper()
                barcode_b64 = get_barcode_image_base64(mvd_hoa)
                
                # HTML Phong bì B5 ngang chuẩn vị trí tuyệt đối mm
                envelope_html = f"""
                <div class="b5-envelope">
                    <!-- NGƯỜI GỬI: Cách trái 10mm, cách trên 35mm -->
                    <div class="sender-info">
                        <b>NGƯỜI GỬI: BHXH TỈNH NGHỆ AN</b><br>
                        Địa chỉ: Số 06, đường Trường Thi, TP Vinh, Nghệ An<br>
                        Điện thoại: 0238.3844888
                    </div>
                    
                    <!-- Ô CHỈ DẪN PHÁT (65mm x 20mm): Cách trái 10mm, cách trên 65mm -->
                    <div class="notice-box">
                        PHÁT ĐỒNG KIỂM, THU HỒI<br>"MẪU 05" TRONG PHONG BÌ
                    </div>
                    
                    <!-- MÃ VẬN ĐƠN: Cách trái 110mm, cách trên 60mm -->
                    <div class="barcode-area">
                        <div style="font-size: 12px; font-weight: bold; margin-bottom: 2px;">
                            Mã vận đơn bưu điện:
                        </div>
                        {f'<img src="{barcode_b64}" style="max-height: 45px; width: 190px; object-fit: contain;" />' if barcode_b64 else ''}
                        <div style="font-size: 14px; font-weight: bold; letter-spacing: 1.5px; margin-top: 2px;">
                            {mvd_hoa}
                        </div>
                    </div>
                    
                    <!-- THÔNG TIN NGƯỜI NHẬN: Cách trái 100mm, cách trên 95mm -->
                    <div class="receiver-info">
                        <b>Kính gửi:</b> <span style="font-size: 15px; font-weight: bold;">{row['ten_don_vi']}</span><br>
                        <b>Mã đơn vị:</b> {row['ma_don_vi']}<br>
                        <b>Địa chỉ:</b> {row['dia_chi']}<br>
                        <b>Điện thoại:</b> {row['dien_thoai']}<br>
                        <b>Nội dung gửi:</b> {row['noi_dung_gui']}<br>
                        <b>Số bản kê 05:</b> {row['so_ban_ke']}
                    </div>
                </div>
                """
                html_print_all += envelope_html
                
            html_print_all += '</div>'
            st.markdown(html_print_all, unsafe_allow_html=True)
    else:
        st.info("Không tìm thấy dữ liệu hồ sơ phù hợp trong khoảng thời gian này.")

# ------------------------------------------
# TAB 3: THEO DÕI & THU HỒI BIÊN BẢN (MẪU 05)
# ------------------------------------------
with tab3:
    st.subheader("Theo dõi & Thu hồi biên bản Mẫu 05")
    
    col_left, col_right = st.columns([1, 1.2])
    
    # NỬA TRÁI: Quét mã vạch sohieu để cập nhật ngày thu hồi & ghi chú
    with col_left:
        st.markdown("### 🔍 Quét mã vạch cập nhật thu hồi")
        with st.form("form_scan_m05", clear_on_submit=True):
            scan_code_raw = st.text_input("Quét/Nhập Mã vận đơn (Số hiệu bưu gửi):", placeholder="Đưa đầu đọc mã vạch vào đây...")
            ngay_thu_hoi = st.date_input("Ngày thu hồi (trangthaiphat):", value=datetime.now().date())
            ghi_chu = st.text_area("Ghi chú thu hồi:", placeholder="Nhập ghi chú (nếu có)...", height=80)
            
            btn_confirm_scan = st.form_submit_button("✅ Cập Nhật Thu Hồi Mẫu 05", type="primary", use_container_width=True)
            
            if btn_confirm_scan:
                scan_code = scan_code_raw.strip().upper()
                if not scan_code:
                    st.warning("⚠️ Vui lòng quét mã vận đơn!")
                else:
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        update_query = """
                            UPDATE quanly_hoso 
                            SET trang_thai_m05 = 'Đã thu hồi',
                                ngay_thu_hoi = %s,
                                ghi_chu = %s
                            WHERE UPPER(ma_van_don) = %s;
                        """
                        cursor.execute(update_query, (ngay_thu_hoi, ghi_chu, scan_code))
                        conn.commit()
                        if cursor.rowcount > 0:
                            st.success(f"🎉 Đã thu hồi biên bản Mẫu 05 cho mã {scan_code} thành công!")
                        else:
                            st.error(f"❌ Không tìm thấy mã vận đơn {scan_code} trong CSDL!")
                        cursor.close()
                    except Exception as e:
                        st.error(f"Lỗi cập nhật CSDL: {e}")

    # NỬA PHẢI: Bảng cảnh báo danh sách chưa thu hồi (Xếp theo ngày gửi lâu nhất nằm trên)
    with col_right:
        st.markdown("### ⚠️ Cảnh báo Mẫu 05 CHƯA thu hồi (Ưu tiên đôn đốc)")
        
        try:
            conn = get_db_connection()
            # Tự động sắp xếp ngày nhận/gửi tăng dần (lâu nhất nằm trên)
            alert_query = """
                SELECT ma_van_don, ten_don_vi, ma_don_vi, ngay_nhan as ngay_gui, dien_thoai
                FROM quanly_hoso 
                WHERE trang_thai_m05 IS NULL OR trang_thai_m05 != 'Đã thu hồi'
                ORDER BY ngay_nhan ASC;
            """
            df_alert = pd.read_sql_query(alert_query, conn)
            
            if not df_alert.empty:
                st.warning(f"Hiện có **{len(df_alert)}** hồ sơ chưa thu hồi Mẫu 05!")
                st.dataframe(
                    df_alert,
                    column_config={
                        "ma_van_don": "Mã vận đơn",
                        "ten_don_vi": "Tên đơn vị",
                        "ma_don_vi": "Mã ĐV",
                        "ngay_gui": st.column_config.DateColumn("Ngày gửi", format="DD/MM/YYYY"),
                        "dien_thoai": "SĐT liên hệ"
                    },
                    use_container_width=True,
                    height=400
                )
            else:
                st.balloons()
                st.success("Tất cả biên bản Mẫu 05 đã được thu hồi hoàn tất!")
        except Exception as e:
            st.error(f"Lỗi tải danh sách cảnh báo: {e}")