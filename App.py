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
    
    /* Khung phong bì B5 Ngang tiêu chuẩn (235mm x 165mm) */
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
    
    /* CSS hỗ trợ in ấn hàng loạt */
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
    code_clean = str(code_text).strip().upper()
    if not code_clean:
        return ""
    try:
        code128 = barcode.get_barcode_class('code128')
        rv = io.BytesIO()
        writer_options = {'write_text': False, 'module_height': 12.0, 'module_width': 0.35, 'quiet_zone': 2.0}
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
        conn = init_connection()
        conn.rollback()
        return conn
    except Exception:
        st.cache_resource.clear()
        conn = init_connection()
        conn.rollback()
        return conn

def init_db_tables():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dm_donvi (
                ma_don_vi VARCHAR(50) PRIMARY KEY,
                ten_don_vi TEXT,
                dia_chi TEXT,
                dien_thoai VARCHAR(100)
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quanly_hoso (
                id SERIAL PRIMARY KEY,
                ngay_nhan DATE,
                ma_van_don VARCHAR(100),
                ten_don_vi TEXT,
                ma_don_vi VARCHAR(50),
                dia_chi TEXT,
                dien_thoai VARCHAR(100),
                noi_dung_gui TEXT,
                so_ban_ke VARCHAR(50),
                trang_thai_m05 VARCHAR(50) DEFAULT 'Chưa thu hồi',
                ngay_thu_hoi DATE,
                ghi_chu TEXT
            );
        """)
        conn.commit()
        cursor.close()
    except Exception:
        conn.rollback()

init_db_tables()

def load_dm_donvi():
    try:
        conn = get_db_connection()
        return pd.read_sql_query("SELECT ma_don_vi, ten_don_vi, dia_chi, dien_thoai FROM dm_donvi ORDER BY ma_don_vi;", conn)
    except Exception:
        return pd.DataFrame(columns=["ma_don_vi", "ten_don_vi", "dia_chi", "dien_thoai"])

def save_or_update_dm_donvi(ma_dv, ten_dv, dia_chi, dien_thoai):
    if not ma_dv.strip():
        return False
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
        cursor.execute(query, (ma_dv.strip(), ten_dv.strip(), dia_chi.strip(), dien_thoai.strip()))
        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Lỗi cập nhật danh mục đơn vị: {e}")
        return False

def load_hoso_data(from_date=None, to_date=None, search_term=""):
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
        return pd.read_sql_query(query, conn, params=params)
    except Exception:
        conn.rollback()
        return pd.DataFrame()

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
# TAB 1: NHẬP HỒ SƠ & LOGIC XỬ LÝ ĐƠN VỊ
# ------------------------------------------
with tab1:
    st.subheader("Nhập hồ sơ gửi & Cập nhật Danh mục Đơn vị")
    
    df_dm = load_dm_donvi()
    
    # 1. Ô tìm kiếm đơn vị
    search_dv = st.text_input("🔍 Gõ Tên hoặc Mã đơn vị để tìm kiếm từ DM_donvi:", key="search_dv_tab1").strip()
    
    selected_unit = None
    
    if not df_dm.empty:
        if search_dv:
            filtered_dm = df_dm[
                df_dm['ma_don_vi'].astype(str).str.contains(search_dv, case=False, na=False) |
                df_dm['ten_don_vi'].astype(str).str.contains(search_dv, case=False, na=False)
            ]
        else:
            filtered_dm = df_dm
            
        if not filtered_dm.empty:
            options = ["-- Chọn đơn vị từ danh sách gợi ý --"] + [
                f"{row['ma_don_vi']} - {row['ten_don_vi']}" for _, row in filtered_dm.iterrows()
            ]
            
            selected_option = st.selectbox("Danh sách đơn vị phù hợp (Bấm chọn để tự động điền):", options=options)
            
            if selected_option != "-- Chọn đơn vị từ danh sách gợi ý --":
                sel_code = selected_option.split(" - ")[0]
                selected_unit = df_dm[df_dm['ma_don_vi'] == sel_code].iloc[0]
                st.info("💡 Đã tự động điền thông tin đơn vị. Bạn có thể chỉnh sửa Mã, Địa chỉ, SĐT bên dưới trước khi bấm Lưu.")
        else:
            st.warning("⚠️ Không tìm thấy đơn vị trong DM_donvi. Nhập Mã đơn vị bên dưới nếu muốn THÊM MỚI vào danh mục.")
    else:
        st.info("💡 Danh mục DM_donvi hiện chưa có dữ liệu. Hãy nhập thông tin bên dưới để thêm đơn vị đầu tiên.")

    # Form nhập liệu
    with st.form("form_tab1", clear_on_submit=False):
        col1, col2 = st.columns(2)
        default_ngay_nhan = datetime.now().date() - timedelta(days=1)
        
        with col1:
            # 1. Mã đơn vị
            ma_don_vi = st.text_input(
                "1. Mã đơn vị (Bắt buộc nếu muốn lưu/sửa DM_donvi):", 
                value=selected_unit['ma_don_vi'] if selected_unit is not None else ""
            )
            
            # 2. Tên đơn vị
            ten_don_vi = st.text_input(
                "2. Tên đơn vị / Người nhận:", 
                value=selected_unit['ten_don_vi'] if selected_unit is not None else search_dv
            )
            
            # 3. Địa chỉ
            dia_chi = st.text_area(
                "3. Địa chỉ:", 
                value=selected_unit['dia_chi'] if selected_unit is not None else "", 
                height=100
            )
            
            # 4. Điện thoại
            dien_thoai = st.text_input(
                "4. Điện thoại:", 
                value=selected_unit['dien_thoai'] if selected_unit is not None else ""
            )

        with col2:
            # 5. Ngày nhận gửi (Mặc định lùi 1 ngày)
            ngay_nhan = st.date_input("5. Ngày nhận gửi (Mặc định lùi 1 ngày):", value=default_ngay_nhan)
            
            # 6. Số hiệu bản kê
            so_ban_ke = st.text_input("6. Số hiệu bản kê 05:", value="111")
            
            # 7. Nội dung (Loại hồ sơ)
            loai_ho_so = st.selectbox("7. Nội dung gửi (Loại hồ sơ):", DANH_SACH_LOAI_HO_SO)
            
            # 8. Số hiệu bưu gửi / Mã vận đơn
            ma_van_don_raw = st.text_input("8. Số hiệu bưu gửi / Mã vận đơn (Cho phép quét):", placeholder="Nhập/quét mã bưu gửi...")
            
        btn_save_tab1 = st.form_submit_button("💾 Lưu Hồ Sơ & Xử Lý Danh Mục Đơn Vị", type="primary", use_container_width=True)
        
        if btn_save_tab1:
            ma_van_don = ma_van_don_raw.strip().upper()
            if not ma_van_don or not ten_don_vi:
                st.warning("⚠️ Vui lòng điền Tên đơn vị và Số hiệu bưu gửi (Mã vận đơn)!")
            else:
                try:
                    dm_updated = False
                    if ma_don_vi.strip():
                        dm_updated = save_or_update_dm_donvi(ma_don_vi, ten_don_vi, dia_chi, dien_thoai)
                    
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    insert_query = """
                        INSERT INTO quanly_hoso 
                        (ngay_nhan, ma_van_don, ten_don_vi, ma_don_vi, dia_chi, dien_thoai, noi_dung_gui, so_ban_ke, trang_thai_m05)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    cursor.execute(insert_query, (
                        ngay_nhan, ma_van_don, ten_don_vi, ma_don_vi.strip(), 
                        dia_chi, dien_thoai, loai_ho_so, so_ban_ke, "Chưa thu hồi"
                    ))
                    conn.commit()
                    cursor.close()
                    
                    if dm_updated:
                        st.success(f"✅ Đã lưu hồ sơ {ma_van_don} và ĐỒNG BỘ CẬP NHẬT đơn vị {ma_don_vi} vào danh mục DM_donvi!")
                    else:
                        st.success(f"✅ Đã lưu hồ sơ gửi 1 lần {ma_van_don} (Không cập nhật DM_donvi do không có Mã đơn vị).")
                except Exception as e:
                    st.error(f"❌ Lỗi khi lưu dữ liệu: {e}")

    # Bảng hiển thị danh sách hồ sơ mới nhập
    st.divider()
    st.subheader("Danh sách hồ sơ mới nhập")
    df_hoso_tab1 = load_hoso_data()
    if not df_hoso_tab1.empty:
        display_df = df_hoso_tab1[['ma_don_vi', 'ten_don_vi', 'dia_chi', 'ma_van_don', 'ngay_nhan', 'noi_dung_gui']].copy()
        display_df.insert(0, 'STT', range(1, len(display_df) + 1))
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("Chưa có dữ liệu hồ sơ.")

# ------------------------------------------
# TAB 2: THỐNG KÊ & IN PHONG BÌ
# ------------------------------------------
with tab2:
    st.subheader("Thống kê hồ sơ & In phong bì B5 ngang (235mm x 165mm)")
    
    col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
    with col_f1:
        from_date = st.date_input("Từ ngày:", value=datetime.now().date() - timedelta(days=30))
    with col_f2:
        to_date = st.date_input("Đến ngày:", value=datetime.now().date())
    with col_f3:
        search_keyword = st.text_input("Từ khóa (Mã vận đơn, Tên/Mã đơn vị):", "")
        
    df_tab2 = load_hoso_data(from_date=from_date, to_date=to_date, search_term=search_keyword)
    
    if not df_tab2.empty:
        select_all = st.checkbox("Select All / Chọn tất cả hồ sơ")
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
        with col_act1:
            if not selected_rows.empty:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    selected_rows.drop(columns=["Chon"]).to_excel(writer, index=False, sheet_name='Danh_Sach_In')
                st.download_button(
                    label=f"📥 Xuất Excel ({len(selected_rows)} hồ sơ đã chọn)",
                    data=buffer.getvalue(),
                    file_name=f"DS_Ho_So_BHXH_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        with col_act2:
            show_print_view = st.button(f"🖨️ Tạo phôi in B5 ({len(selected_rows)} hồ sơ)", type="primary", use_container_width=True)
            
        if show_print_view and not selected_rows.empty:
            html_print_all = '<div class="print-area">'
            for _, row in selected_rows.iterrows():
                mvd_hoa = str(row['ma_van_don']).upper()
                barcode_b64 = get_barcode_image_base64(mvd_hoa)
                envelope_html = f"""
                <div class="b5-envelope">
                    <div class="sender-info">
                        <b>NGƯỜI GỬI: BHXH TỈNH NGHỆ AN</b><br>
                        Địa chỉ: Số 06, đường Trường Thi, TP Vinh, Nghệ An<br>
                        Điện thoại: 0238.3844888
                    </div>
                    <div class="notice-box">
                        PHÁT ĐỒNG KIỂM, THU HỒI<br>"MẪU 05" TRONG PHONG BÌ
                    </div>
                    <div class="barcode-area">
                        <div style="font-size: 12px; font-weight: bold; margin-bottom: 2px;">Mã vận đơn bưu điện:</div>
                        {f'<img src="{barcode_b64}" style="max-height: 45px; width: 190px; object-fit: contain;" />' if barcode_b64 else ''}
                        <div style="font-size: 14px; font-weight: bold; letter-spacing: 1.5px; margin-top: 2px;">{mvd_hoa}</div>
                    </div>
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

# ------------------------------------------
# TAB 3: THEO DÕI & THU HỒI MẪU 05
# ------------------------------------------
with tab3:
    st.subheader("Theo dõi & Thu hồi biên bản Mẫu 05")
    col_left, col_right = st.columns([1, 1.2])
    with col_left:
        st.markdown("### 🔍 Quét mã vạch cập nhật thu hồi")
        with st.form("form_scan_m05", clear_on_submit=True):
            scan_code_raw = st.text_input("Quét/Nhập Mã vận đơn (Số hiệu bưu gửi):")
            ngay_thu_hoi = st.date_input("Ngày thu hồi:", value=datetime.now().date())
            ghi_chu = st.text_area("Ghi chú thu hồi:", height=80)
            btn_confirm_scan = st.form_submit_button("✅ Cập Nhật Thu Hồi Mẫu 05", type="primary", use_container_width=True)
            if btn_confirm_scan:
                scan_code = scan_code_raw.strip().upper()
                if scan_code:
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE quanly_hoso SET trang_thai_m05 = 'Đã thu hồi', ngay_thu_hoi = %s, ghi_chu = %s WHERE UPPER(ma_van_don) = %s;", (ngay_thu_hoi, ghi_chu, scan_code))
                        conn.commit()
                        st.success(f"🎉 Đã thu hồi Mẫu 05 cho mã {scan_code}!")
                        cursor.close()
                    except Exception as e:
                        st.error(f"Lỗi cập nhật: {e}")
    with col_right:
        st.markdown("### ⚠️ Cảnh báo Mẫu 05 CHƯA thu hồi")
        try:
            conn = get_db_connection()
            df_alert = pd.read_sql_query("SELECT ma_van_don, ten_don_vi, ma_don_vi, ngay_nhan as ngay_gui, dien_thoai FROM quanly_hoso WHERE trang_thai_m05 IS NULL OR trang_thai_m05 != 'Đã thu hồi' ORDER BY ngay_nhan ASC;", conn)
            if not df_alert.empty:
                st.warning(f"Hiện có **{len(df_alert)}** hồ sơ chưa thu hồi Mẫu 05!")
                st.dataframe(df_alert, use_container_width=True)
            else:
                st.success("Tất cả biên bản Mẫu 05 đã được thu hồi!")
        except Exception as e:
            st.error(f"Lỗi tải dữ liệu: {e}")