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

# Custom CSS cho phong bì B5 ngang, bảng dữ liệu kẻ khung và giao diện cửa sổ thao tác
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

    .action-window {
        background-color: #f8fafc;
        border: 2px solid #0066cc;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
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
        connect_timeout=5
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
            CREATE TABLE IF NOT EXISTS "DM_donvi" (
                "maDV" VARCHAR(50) PRIMARY KEY,
                "tenDV" TEXT,
                "diachidv" TEXT,
                "dienthoai" VARCHAR(100)
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

# Tải danh mục vào Session State để loại bỏ độ trễ mạng Supabase
def load_dm_donvi_fast():
    if 'cached_dm_donvi' not in st.session_state:
        try:
            conn = get_db_connection()
            query = 'SELECT COALESCE("maDV", \'\') as ma_don_vi, "tenDV" as ten_don_vi, "diachidv" as dia_chi, "dienthoai" as dien_thoai FROM "DM_donvi" ORDER BY "tenDV";'
            df = pd.read_sql_query(query, conn)
            df['ma_don_vi'] = df['ma_don_vi'].fillna('').astype(str).str.strip()
            df['ten_don_vi'] = df['ten_don_vi'].fillna('').astype(str).str.strip()
            df['dia_chi'] = df['dia_chi'].fillna('').astype(str).str.strip()
            df['dien_thoai'] = df['dien_thoai'].fillna('').astype(str).str.strip()
            st.session_state['cached_dm_donvi'] = df
        except Exception as e:
            st.error(f"Lỗi tải DM_donvi: {e}")
            st.session_state['cached_dm_donvi'] = pd.DataFrame(columns=["ma_don_vi", "ten_don_vi", "dia_chi", "dien_thoai"])
    return st.session_state['cached_dm_donvi']

def save_or_update_dm_donvi(ma_dv, ten_dv, dia_chi, dien_thoai):
    if not ma_dv.strip():
        return False
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO "DM_donvi" ("maDV", "tenDV", "diachidv", "dienthoai")
            VALUES (%s, %s, %s, %s)
            ON CONFLICT ("maDV") 
            DO UPDATE SET 
                "tenDV" = EXCLUDED."tenDV",
                "diachidv" = EXCLUDED."diachidv",
                "dienthoai" = EXCLUDED."dienthoai";
        """
        cursor.execute(query, (ma_dv.strip(), ten_dv.strip(), dia_chi.strip(), dien_thoai.strip()))
        conn.commit()
        cursor.close()
        # Xóa cache session để cập nhật dữ liệu mới lập tức
        if 'cached_dm_donvi' in st.session_state:
            del st.session_state['cached_dm_donvi']
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Lỗi cập nhật danh mục đơn vị: {e}")
        return False

def load_hoso_data_fast(search_term=""):
    try:
        conn = get_db_connection()
        query = "SELECT * FROM quanly_hoso WHERE 1=1"
        params = []
        if search_term:
            query += " AND (ma_van_don ILIKE %s OR ten_don_vi ILIKE %s OR ma_don_vi ILIKE %s)"
            pattern = f"%{search_term}%"
            params.extend([pattern, pattern, pattern])
        query += " ORDER BY id DESC LIMIT 500;"
        df = pd.read_sql_query(query, conn, params=params)
        return df
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
    
    df_dm = load_dm_donvi_fast()

    unit_options = ["-- Chọn hoặc gõ tên/mã đơn vị bên dưới --"]
    unit_dict = {}
    if not df_dm.empty:
        for _, row in df_dm.iterrows():
            code_str = f"[{row['ma_don_vi']}] " if row['ma_don_vi'] else ""
            display_text = f"{code_str}{row['ten_don_vi']}"
            unit_options.append(display_text)
            unit_dict[display_text] = row

    selected_option = st.selectbox(
        "🔍 Gõ Mã hoặc Tên đơn vị để tìm kiếm nhanh từ DM_donvi:",
        options=unit_options,
        key="sb_select_unit_tab1"
    )

    selected_unit = None
    if selected_option != "-- Chọn hoặc gõ tên/mã đơn vị bên dưới --" and selected_option in unit_dict:
        selected_unit = unit_dict[selected_option]

    form_key_suffix = selected_unit['ma_don_vi'] if selected_unit is not None and selected_unit['ma_don_vi'] else "new"

    with st.form("form_tab1", clear_on_submit=False):
        col1, col2 = st.columns(2)
        default_ngay_nhan = datetime.now().date() - timedelta(days=1)
        
        with col1:
            ma_don_vi = st.text_input(
                "1. Mã đơn vị (Bắt buộc nếu muốn lưu/sửa DM_donvi):", 
                value=selected_unit['ma_don_vi'] if selected_unit is not None else ""
            )
            ten_don_vi = st.text_input(
                "2. Tên đơn vị / Người nhận:", 
                value=selected_unit['ten_don_vi'] if selected_unit is not None else ""
            )
            dia_chi = st.text_area(
                "3. Địa chỉ:", 
                value=selected_unit['dia_chi'] if selected_unit is not None else "", 
                height=100
            )
            dien_thoai = st.text_input(
                "4. Điện thoại:", 
                value=selected_unit['dien_thoai'] if selected_unit is not None else ""
            )

        with col2:
            ngay_nhan = st.date_input("5. Ngày nhận gửi (Mặc định lùi 1 ngày):", value=default_ngay_nhan, format="DD/MM/YYYY")
            so_ban_ke = st.text_input("6. Số hiệu bản kê 05:", value="", placeholder="Nhập số bản kê...", key=f"sbk_{form_key_suffix}")
            loai_ho_so = st.selectbox("7. Nội dung gửi (Loại hồ sơ):", DANH_SACH_LOAI_HO_SO)
            ma_van_don_raw = st.text_input("8. Số hiệu bưu gửi / Mã vận đơn (Quét mã vạch):", value="", placeholder="Nhập/quét mã bưu gửi...", key=f"mvd_{form_key_suffix}")
            
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

    st.divider()
    st.subheader("Danh sách hồ sơ mới nhập")
    df_hoso_tab1 = load_hoso_data_fast()
    if not df_hoso_tab1.empty:
        display_df = df_hoso_tab1[['ma_don_vi', 'ten_don_vi', 'dia_chi', 'ma_van_don', 'ngay_nhan', 'noi_dung_gui']].copy()
        display_df['ngay_nhan'] = pd.to_datetime(display_df['ngay_nhan']).dt.strftime('%d/%m/%Y')
        display_df.insert(0, 'STT', range(1, len(display_df) + 1))
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("Chưa có dữ liệu hồ sơ.")

# ------------------------------------------
# TAB 2: THỐNG KÊ, SỬA/XÓA & IN PHONG BÌ
# ------------------------------------------
with tab2:
    st.subheader("Thống kê hồ sơ & Quản lý in/sửa/xóa")
    
    col_f1, col_f2 = st.columns([1, 2])
    with col_f1:
        search_keyword = st.text_input("🔍 Tìm kiếm nhanh (Số hiệu, Tên đơn vị):", "", key="f_keyword_fast")
    with col_f2:
        st.write("")
        st.markdown("💡 *Hệ thống đã lưu cache dữ liệu giúp thao tác in và sửa phản hồi ngay lập tức.*")
        
    df_tab2 = load_hoso_data_fast(search_term=search_keyword)
    
    if not df_tab2.empty:
        if 'active_action' not in st.session_state:
            st.session_state['active_action'] = None
        if 'active_id' not in st.session_state:
            st.session_state['active_id'] = None

        if st.session_state['active_action'] == 'edit' and st.session_state['active_id'] is not None:
            match_edit = df_tab2[df_tab2['id'] == st.session_state['active_id']]
            if not match_edit.empty:
                row_edit = match_edit.iloc[0]
                st.markdown('<div class="action-window">', unsafe_allow_html=True)
                col_ew1, col_ew2 = st.columns([8, 1])
                col_ew1.warning(f"📝 **Đang chỉnh sửa hồ sơ:** {row_edit['ma_van_don']}")
                if col_ew2.button("❌ Đóng", key="close_edit_win"):
                    st.session_state['active_action'] = None
                    st.session_state['active_id'] = None
                    st.rerun()

                with st.form("form_edit_fast"):
                    ce1, ce2 = st.columns(2)
                    with ce1:
                        e_ngay = st.date_input("Ngày nhận gửi:", value=pd.to_datetime(row_edit['ngay_nhan']).date(), format="DD/MM/YYYY")
                        e_mvd = st.text_input("Số hiệu bưu gửi:", value=row_edit['ma_van_don'])
                        e_madv = st.text_input("Mã đơn vị:", value=str(row_edit['ma_don_vi'] or ''))
                        e_tendv = st.text_input("Tên đơn vị:", value=row_edit['ten_don_vi'])
                    with ce2:
                        e_dc = st.text_area("Địa chỉ:", value=str(row_edit['dia_chi'] or ''), height=100)
                        e_dt = st.text_input("Điện thoại:", value=str(row_edit['dien_thoai'] or ''))
                        e_loai = st.selectbox("Nội dung gửi:", DANH_SACH_LOAI_HO_SO, index=DANH_SACH_LOAI_HO_SO.index(row_edit['noi_dung_gui']) if row_edit['noi_dung_gui'] in DANH_SACH_LOAI_HO_SO else 0)
                        e_sbk = st.text_input("Số bản kê 05:", value=str(row_edit['so_ban_ke'] or ''))
                        
                    if st.form_submit_button("💾 Lưu Thay Đổi", type="primary", use_container_width=True):
                        try:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE quanly_hoso 
                                SET ngay_nhan = %s, ma_van_don = %s, ma_don_vi = %s, ten_don_vi = %s, 
                                    dia_chi = %s, dien_thoai = %s, noi_dung_gui = %s, so_ban_ke = %s
                                WHERE id = %s;
                            """, (e_ngay, e_mvd.strip().upper(), e_madv, e_tendv, e_dc, e_dt, e_loai, e_sbk, row_edit['id']))
                            conn.commit()
                            cursor.close()
                            st.session_state['active_action'] = None
                            st.session_state['active_id'] = None
                            st.success("✅ Cập nhật thành công!")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Lỗi: {ex}")
                st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state['active_action'] == 'print' and st.session_state['active_id'] is not None:
            match_print = df_tab2[df_tab2['id'] == st.session_state['active_id']]
            if not match_print.empty:
                row_p = match_print.iloc[0]
                st.markdown('<div class="action-window">', unsafe_allow_html=True)
                cp1, cp2, cp3 = st.columns([5, 2, 1])
                cp1.write(f"🖨️ **Cửa sổ in phôi B5 ngang:** `{row_p['ma_van_don']}`")
                
                if cp2.button("🖨️ Gửi lệnh in ngay", type="primary", key="trigger_browser_print"):
                    st.markdown('<script>window.print();</script>', unsafe_allow_html=True)
                    st.session_state['active_action'] = None
                    st.session_state['active_id'] = None
                    st.rerun()
                    
                if cp3.button("❌ Đóng", key="close_print_win"):
                    st.session_state['active_action'] = None
                    st.session_state['active_id'] = None
                    st.rerun()

                mvd_hoa = str(row_p['ma_van_don']).upper()
                barcode_b64 = get_barcode_image_base64(mvd_hoa)
                
                envelope_html = f"""
                <div class="print-area">
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
                            {f'<img src="{barcode_b64}" style="max-height: 48px; width: 190px; object-fit: contain;" />' if barcode_b64 else ''}
                            <div style="font-size: 14px; font-weight: bold; letter-spacing: 1.5px; margin-top: 4px;">{mvd_hoa}</div>
                        </div>
                        <div class="receiver-info">
                            <b>Kính gửi:</b> <span style="font-size: 15px; font-weight: bold;">{row_p['ten_don_vi']}</span><br>
                            <b>Mã đơn vị:</b> {row_p['ma_don_vi']}<br>
                            <b>Địa chỉ:</b> {row_p['dia_chi']}<br>
                            <b>Điện thoại:</b> {row_p['dien_thoai']}<br>
                            <b>Nội dung gửi:</b> {row_p['noi_dung_gui']}<br>
                            <b>Số bản kê 05:</b> {row_p['so_ban_ke']}
                        </div>
                    </div>
                </div>
                """
                st.markdown(envelope_html, unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

        st.write(f"**Danh sách kết quả ({len(df_tab2)} hồ sơ):**")
        
        for idx, row in df_tab2.reset_index(drop=True).iterrows():
            ngay_str = pd.to_datetime(row['ngay_nhan']).strftime('%d/%m/%Y') if pd.notnull(row['ngay_nhan']) else ""
            c_info, c_in, c_sua, c_xoa = st.columns([5.5, 1, 1, 1])
            
            c_info.write(f"**[{idx+1}] {row['ma_van_don']}** — {row['ten_don_vi']} *({ngay_str})*")
            
            if c_in.button("🖨️ In", key=f"fast_in_{row['id']}"):
                st.session_state['active_action'] = 'print'
                st.session_state['active_id'] = row['id']
                st.rerun()
                
            if c_sua.button("✏️ Sửa", key=f"fast_sua_{row['id']}"):
                st.session_state['active_action'] = 'edit'
                st.session_state['active_id'] = row['id']
                st.rerun()
                
            if c_xoa.button("🗑️ Xóa", key=f"fast_xoa_{row['id']}"):
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM quanly_hoso WHERE id = %s;", (row['id'],))
                    conn.commit()
                    cursor.close()
                    st.success(f"✅ Đã xóa hồ sơ {row['ma_van_don']}!")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Lỗi: {ex}")

        st.divider()
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_tab2.to_excel(writer, index=False, sheet_name='Danh_Sach_Tim_Kiem')
        st.download_button(
            label=f"📥 Xuất Excel danh sách ({len(df_tab2)} hồ sơ)",
            data=buffer.getvalue(),
            file_name=f"DS_Ho_So_BHXH_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    else:
        st.info("Không tìm thấy dữ liệu hồ sơ phù hợp.")

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
            ngay_thu_hoi = st.date_input("Ngày thu hồi:", value=datetime.now().date(), format="DD/MM/YYYY")
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
        st.markdown("### ⚠️ Cảnh báo Mẫu 05 CHƯA thu hồi (Ưu tiên đôn đốc)")
        try:
            conn = get_db_connection()
            df_alert = pd.read_sql_query("SELECT ma_van_don, ten_don_vi, ma_don_vi, ngay_nhan as ngay_gui, dien_thoai FROM quanly_hoso WHERE trang_thai_m05 IS NULL OR trang_thai_m05 != 'Đã thu hồi' ORDER BY ngay_nhan ASC;", conn)
            if not df_alert.empty:
                df_alert['ngay_gui'] = pd.to_datetime(df_alert['ngay_gui']).dt.strftime('%d/%m/%Y')
                st.warning(f"Hiện có **{len(df_alert)}** hồ sơ chưa thu hồi Mẫu 05!")
                st.dataframe(df_alert, use_container_width=True)
            else:
                st.success("Tất cả biên bản Mẫu 05 đã được thu hồi!")
        except Exception as e:
            st.error(f"Lỗi tải dữ liệu: {e}")