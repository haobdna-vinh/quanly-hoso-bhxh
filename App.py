import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime, date, timedelta
import io

# ---------------------------------------------------------
# 1. CẤU HÌNH TRANG WEB & TẢI CUSTOM CSS GIAO DIỆN
# ---------------------------------------------------------
st.set_page_config(
    page_title="Hệ thống Quản lý Hồ sơ BHXH",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS Nâng cấp Giao diện
st.markdown("""
<style>
    .main {
        background-color: #f8fafc;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    .app-header {
        background: linear-gradient(135deg, #1e3a8a 0%, #0284c7 100%);
        padding: 24px;
        border-radius: 12px;
        color: white;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .app-header h1 {
        color: white !important;
        margin: 0;
        font-size: 26px;
        font-weight: 700;
    }
    .app-header p {
        color: #e0f2fe;
        margin: 6px 0 0 0;
        font-size: 14px;
    }

    .metric-card {
        background-color: white;
        padding: 16px 20px;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        text-align: center;
    }
    .metric-card .title {
        font-size: 13px;
        color: #64748b;
        font-weight: 600;
        text-transform: uppercase;
    }
    .metric-card .value {
        font-size: 24px;
        font-weight: 700;
        color: #0f172a;
        margin-top: 4px;
    }

    div.stButton > button {
        border-radius: 6px;
        font-weight: 600;
        transition: all 0.2s;
    }
    div.stButton > button:hover {
        transform: translateY(-1px);
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. KẾT NỐI POSTGRESQL CLOUD (SUPABASE / NEON)
# ---------------------------------------------------------
@st.cache_resource
def init_connection():
    return psycopg2.connect(
        host=st.secrets["postgres"]["host"],
        port=st.secrets["postgres"]["port"],
        database=st.secrets["postgres"]["database"],
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"],
        sslmode="require",  # <-- BẮT BUỘC có dòng này đối với PostgreSQL Cloud
        connect_timeout=10
    )
def get_db_connection():
    try:
        conn = init_connection()
        if conn.closed != 0:
            st.cache_resource.clear()
            conn = init_connection()
        return conn
    except Exception:
        st.cache_resource.clear()
        return init_connection()

# ---------------------------------------------------------
# 3. CACHE TẢI DANH MỤC ĐƠN VỊ TỐC ĐỘ CAO
# ---------------------------------------------------------
@st.cache_data(ttl=600)
def get_donvi_options():
    conn = get_db_connection()
    query = 'SELECT "tenDV" AS tendv, "maDV" AS madv, "diachidv", "dienthoai" FROM "DM_donvi" ORDER BY "tenDV" ASC;'
    try:
        df = pd.read_sql_query(query, conn)
        options_map = {}
        for _, row in df.iterrows():
            madv_str = str(row['madv']) if pd.notna(row['madv']) and str(row['madv']).strip() else 'N/A'
            display_str = f"[{madv_str}] - {row['tendv']}"
            if pd.notna(row['diachidv']) and str(row['diachidv']).strip():
                display_str += f" ({row['diachidv']})"
            options_map[display_str] = {
                'madv': str(row['madv']) if pd.notna(row['madv']) else "",
                'tendv': str(row['tendv']) if pd.notna(row['tendv']) else "",
                'diachidv': str(row['diachidv']) if pd.notna(row['diachidv']) else "",
                'dienthoai': str(row['dienthoai']) if pd.notna(row['dienthoai']) else ""
            }
        return options_map
    except Exception:
        conn.rollback()
        return {}

def load_hoso_data(search_kw="", from_date=None, to_date=None):
    conn = get_db_connection()
    query = "SELECT id, madv, tendv, diachidv, dienthoaidv, sobanke, loaihs, noidung, sohieu, trangthaiphat, ghichu, ngaynhan FROM hoso WHERE 1=1"
    
    if search_kw:
        query += f" AND (sohieu ILIKE '%{search_kw}%' OR tendv ILIKE '%{search_kw}%' OR madv ILIKE '%{search_kw}%')"
        
    query += " ORDER BY id DESC;"
    
    try:
        df = pd.read_sql_query(query, conn)
        if 'ngaynhan' in df.columns:
            df['ngaynhan_date'] = pd.to_datetime(df['ngaynhan'], errors='coerce').dt.date
        else:
            df['ngaynhan_date'] = None

        if from_date:
            df = df[df['ngaynhan_date'] >= from_date]
        if to_date:
            df = df[df['ngaynhan_date'] <= to_date]
            
        return df
    except Exception as e:
        conn.rollback()
        st.error(f"Lỗi tải danh sách hồ sơ: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# 4. HÀM TẠO HTML PHONG BÌ B5 (235mm x 165mm)
# ---------------------------------------------------------
def render_envelope_html(hs):
    madv_text = hs.get('madv') if pd.notna(hs.get('madv')) and str(hs.get('madv')).strip() else 'N/A'
    diachi_text = hs.get('diachidv') if pd.notna(hs.get('diachidv')) and str(hs.get('diachidv')).strip() else 'Chưa cập nhật'
    dienthoai_text = hs.get('dienthoaidv') if pd.notna(hs.get('dienthoaidv')) and str(hs.get('dienthoaidv')).strip() else 'Chưa cập nhật'
    sobanke_text = hs.get('sobanke') if pd.notna(hs.get('sobanke')) and str(hs.get('sobanke')).strip() else 'N/A'
    sohieu_text = hs.get('sohieu') if pd.notna(hs.get('sohieu')) else ''
    tendv_text = hs.get('tendv') if pd.notna(hs.get('tendv')) else ''
    
    loaihs_str = str(hs.get('loaihs', ''))
    noidung_str = str(hs.get('noidung', ''))
    noidung_gui = f"{loaihs_str} ({noidung_str})" if noidung_str.strip() else loaihs_str

    html_code = (
        f'<div class="b5-envelope" style="width: 235mm; height: 165mm; border: 2px solid #333; box-sizing: border-box; background-color: #fff; font-family: Arial, sans-serif; color: #000; position: relative; margin: 15px auto; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">'
        f'<div style="position: absolute; top: 35mm; left: 10mm; width: 100mm; font-size: 13px; line-height: 1.4;">'
        f'<b style="font-size: 14px; text-transform: uppercase;">NGƯỜI GỬI: BHXH TỈNH NGHỆ AN</b><br>'
        f'<span>Địa chỉ: Số 06, đường Trường Thi, TP Vinh, Nghệ An</span><br>'
        f'<span>Điện thoại: 0238.3844888</span>'
        f'</div>'
        f'<div style="position: absolute; top: 65mm; left: 10mm; width: 65mm; height: 20mm; border: 1.5px solid #000; box-sizing: border-box; display: flex; align-items: center; justify-content: center; text-align: center; padding: 2px;">'
        f'<span style="font-weight: bold; font-size: 11px; line-height: 1.25; text-transform: uppercase;">'
        f'PHÁT ĐỒNG KIỂM, THU HỒI<br>"MẪU 05" TRONG PHONG BÌ'
        f'</span>'
        f'</div>'
        f'<div style="position: absolute; top: 60mm; left: 110mm; text-align: left;">'
        f'<span style="font-size: 11px;">Mã vận đơn bưu điện:</span><br>'
        f'<span style="font-size: 20px; font-weight: bold; font-family: \'Courier New\', monospace;">{sohieu_text}</span>'
        f'</div>'
        f'<div style="position: absolute; top: 95mm; left: 100mm; right: 10mm; font-size: 14px; line-height: 1.6;">'
        f'<b style="font-size: 15px;">Kính gửi:</b> '
        f'<span style="font-size: 17px; font-weight: bold; color: #002266; text-transform: uppercase;">{tendv_text}</span><br>'
        f'<b>Mã đơn vị:</b> <span style="font-size: 15px; font-weight: bold;">{madv_text}</span><br>'
        f'<b>Địa chỉ:</b> {diachi_text}<br>'
        f'<b>Điện thoại:</b> {dienthoai_text}<br>'
        f'<b>Nội dung gửi:</b> {noidung_gui}<br>'
        f'<b>Số bản kê 05:</b> {sobanke_text}'
        f'</div>'
        f'</div>'
    )
    return html_code

# HỘP THOẠI DIALOG CHỈNH SỬA HỒ SƠ
@st.dialog("✏️ Chỉnh sửa thông tin hồ sơ")
def edit_hoso_dialog(row):
    with st.form("edit_form"):
        madv = st.text_input("Mã đơn vị", value=row.get('madv', ''))
        tendv = st.text_input("Tên đơn vị", value=row.get('tendv', ''))
        diachidv = st.text_area("Địa chỉ", value=row.get('diachidv', ''))
        dienthoaidv = st.text_input("Điện thoại", value=row.get('dienthoaidv', ''))
        
        # Danh sách loại hồ sơ chuẩn
        loaihs_list = [
            "Sổ chốt BHXH", "Thẻ BHYT", "Hưu trí", "Trợ cấp tai nạn lao động", 
            "Chốt hưu", "Chế độ dưỡng sức", "Chế độ ốm đau", "Chế độ thai sản", 
            "Chế độ tuất", "Điều chỉnh thông tin người lao động", "Bảo hiểm thất nghiệp", 
            "Quyết định hưởng 1 lần", "Tăng lao động", "Giảm lao động", "Loại khác"
        ]
        curr_loaihs = row.get('loaihs', '')
        default_idx = loaihs_list.index(curr_loaihs) if curr_loaihs in loaihs_list else 0
        loaihs = st.selectbox("Loại hồ sơ", loaihs_list, index=default_idx)
        
        default_ngay = row.get('ngaynhan_date') if pd.notna(row.get('ngaynhan_date')) else date.today()
        ngaynhan_input = st.date_input("Ngày nhận hồ sơ", value=default_ngay)
        
        sohieu = st.text_input("Số hiệu bưu gửi", value=row.get('sohieu', ''))
        sobanke = st.text_input("Số bản kê 05", value=row.get('sobanke', ''))
        noidung = st.text_area("Nội dung gửi", value=row.get('noidung', ''))
        
        submitted = st.form_submit_button("💾 Lưu thay đổi", type="primary", use_container_width=True)
        if submitted:
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                query = """
                    UPDATE hoso 
                    SET madv=%s, tendv=%s, diachidv=%s, dienthoaidv=%s, sobanke=%s, loaihs=%s, noidung=%s, sohieu=%s, ngaynhan=%s
                    WHERE id=%s;
                """
                cursor.execute(query, (madv, tendv, diachidv, dienthoaidv, sobanke, loaihs, noidung, sohieu, ngaynhan_input, row['id']))
                conn.commit()
                cursor.close()
                st.cache_data.clear()
                st.success("✅ Đã cập nhật thông tin thành công!")
                st.rerun()
            except Exception as e:
                conn.rollback()
                st.error(f"Lỗi khi lưu dữ liệu: {e}")

# ---------------------------------------------------------
# 5. HEADER BANNER CHUYÊN NGHIỆP
# ---------------------------------------------------------
st.markdown("""
<div class="app-header">
    <h1>🏛️ HỆ THỐNG QUẢN LÝ HỒ SƠ & IN PHONG BÌ BHXH</h1>
    <p>Bảo hiểm xã hội tỉnh Nghệ An — Quản lý chuyển phát và thu hồi Mẫu 05 chuẩn B5</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 6. THẺ THỐNG KÊ KPI METRICS
# ---------------------------------------------------------
df_all = load_hoso_data()
total_hs = len(df_all)
total_da_phat = len(df_all[df_all['trangthaiphat'] == 'Đã phát thành công']) if not df_all.empty else 0
total_thu_hoi = len(df_all[df_all['trangthaiphat'] == 'Đã thu hồi Mẫu 05']) if not df_all.empty else 0

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    st.markdown(f'<div class="metric-card"><div class="title">📦 Tổng bưu gửi đã lập</div><div class="value">{total_hs}</div></div>', unsafe_allow_html=True)
with kpi2:
    st.markdown(f'<div class="metric-card"><div class="title">✅ Đã phát thành công</div><div class="value" style="color:#0284c7;">{total_da_phat}</div></div>', unsafe_allow_html=True)
with kpi3:
    st.markdown(f'<div class="metric-card"><div class="title">🔄 Đã thu hồi Mẫu 05</div><div class="value" style="color:#16a34a;">{total_thu_hoi}</div></div>', unsafe_allow_html=True)
with kpi4:
    st.markdown(f'<div class="metric-card"><div class="title">⏳ Chưa hoàn thành</div><div class="value" style="color:#d97706;">{total_hs - total_da_phat}</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------
# 7. CHUYỂN TABS CHỨC NĂNG
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "➕ 1. Nhập Hồ sơ & Cập nhật Đơn vị", 
    "🖨️ 2. Tra cứu Hồ sơ & In Phong bì B5", 
    "🔄 3. Cập nhật Thu hồi Mẫu 05"
])

# =========================================================
# TAB 1: NHẬP HỒ SƠ & CẬP NHẬT ĐƠN VỊ
# =========================================================
with tab1:
    with st.container(border=True):
        st.subheader("1. Tra cứu & Chọn Đơn vị nhận hồ sơ")

        options_map = get_donvi_options()

        selected_option = st.selectbox(
            "🔍 Nhập Mã hoặc Tên đơn vị để tìm kiếm:",
            options=["-- Chọn hoặc gõ tên/mã đơn vị --"] + list(options_map.keys()),
            index=0,
            key="select_donvi_key"
        )

        if selected_option and selected_option in options_map:
            data = options_map[selected_option]
            madv_val = data['madv']
            tendv_val = data['tendv']
            diachidv_val = data['diachidv']
            dienthoai_val = data['dienthoai']
        else:
            madv_val = ""
            tendv_val = ""
            diachidv_val = ""
            dienthoai_val = ""

    with st.container(border=True):
        st.subheader("2. Thông tin Chi tiết Hồ sơ")

        with st.form("form_hoso", clear_on_submit=False):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### 🏢 Thông tin Đơn vị:")
                madv_input = st.text_input("Mã đơn vị (madv)", value=madv_val)
                tendv_input = st.text_input("Tên đơn vị (tendv) (*)", value=tendv_val)
                diachidv_input = st.text_area("Địa chỉ (diachidv)", value=diachidv_val, height=80)
                dienthoai_input = st.text_input("Điện thoại (dienthoai)", value=dienthoai_val)

            with col2:
                st.markdown("#### 📄 Thông tin Hồ sơ gửi:")
                
                # Tự gợi ý ngày nhận là 1 ngày trước ngày nhập hồ sơ (date.today() - 1 ngày)
                default_ngay_nhan = date.today() - timedelta(days=1)
                ngaynhan_input = st.date_input("📅 Ngày nhận hồ sơ (ngaynhan)", value=default_ngay_nhan)
                
                # Danh sách loại hồ sơ cập nhật theo yêu cầu
                list_loai_hoso = [
                    "Sổ chốt BHXH",
                    "Thẻ BHYT",
                    "Hưu trí",
                    "Trợ cấp tai nạn lao động",
                    "Chốt hưu",
                    "Chế độ dưỡng sức",
                    "Chế độ ốm đau",
                    "Chế độ thai sản",
                    "Chế độ tuất",
                    "Điều chỉnh thông tin người lao động",
                    "Bảo hiểm thất nghiệp",
                    "Quyết định hưởng 1 lần",
                    "Tăng lao động",
                    "Giảm lao động",
                    "Loại khác"
                ]
                loaihs = st.selectbox("Loại hồ sơ (loaihs)", list_loai_hoso)
                
                sobanke = st.text_input("Số bản kê 05 (sobanke)", placeholder="Nhập số bản kê...")
                noidung = st.text_area("Nội dung gửi (noidung)", placeholder="Nhập nội dung trích yếu...", height=80)
                sohieu = st.text_input("📦 Số hiệu bưu gửi (sohieu) (*)", placeholder="Ví dụ: CM469122378VN")

            st.markdown("<br>", unsafe_allow_html=True)
            submit_btn = st.form_submit_button("💾 Lưu Hồ Sơ & Cập Nhật Đơn Vị", use_container_width=True, type="primary")

        if submit_btn:
            if not tendv_input.strip():
                st.error("⚠️ Tên đơn vị không được để trống!")
            elif not sohieu.strip():
                st.error("⚠️ Vui lòng nhập Số hiệu bưu gửi!")
            else:
                conn = get_db_connection()
                try:
                    cursor = conn.cursor()
                    upsert_donvi_query = """
                        INSERT INTO "DM_donvi" ("tenDV", "maDV", "diachidv", "dienthoai")
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT ("tenDV") 
                        DO UPDATE SET 
                            "maDV" = EXCLUDED."maDV",
                            "diachidv" = EXCLUDED."diachidv",
                            "dienthoai" = EXCLUDED."dienthoai";
                    """
                    cursor.execute(upsert_donvi_query, (
                        tendv_input.strip(), madv_input.strip(), diachidv_input.strip(), dienthoai_input.strip()
                    ))

                    insert_hoso_query = """
                        INSERT INTO hoso (madv, tendv, diachidv, dienthoaidv, sobanke, loaihs, noidung, sohieu, ngaynhan)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    cursor.execute(insert_hoso_query, (
                        madv_input.strip(), tendv_input.strip(), diachidv_input.strip(), dienthoai_input.strip(),
                        sobanke.strip(), loaihs, noidung.strip(), sohieu.strip(), ngaynhan_input
                    ))

                    conn.commit()
                    cursor.close()
                    st.cache_data.clear()
                    st.balloons()
                    st.success(f"🎉 Đã lưu hồ sơ cho **{tendv_input}** với Ngày nhận là **{ngaynhan_input.strftime('%d/%m/%Y')}**!")
                except Exception as e:
                    conn.rollback()
                    st.error(f"Lỗi khi lưu dữ liệu vào CSDL: {e}")

# =========================================================
# TAB 2: TRA CỨU, THỐNG KÊ & IN PHONG BÌ B5
# =========================================================
with tab2:
    with st.container(border=True):
        st.subheader("🔍 Tra cứu & Thống kê Hồ sơ đã gửi")
        
        col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
        with col_f1:
            search_kw = st.text_input("🔑 Từ khóa (Mã ĐV / Tên ĐV / Số hiệu bưu gửi):", key="search_tab2")
        with col_f2:
            from_date = st.date_input("📅 Từ ngày:", value=None)
        with col_f3:
            to_date = st.date_input("📅 Đến ngày:", value=None)

    df_hoso = load_hoso_data(search_kw, from_date, to_date)
    
    if not df_hoso.empty:
        if "selected_ids" not in st.session_state:
            st.session_state.selected_ids = []

        col_act1, col_act2, col_act3 = st.columns([1.5, 2, 2])
        
        all_selected = len(st.session_state.selected_ids) == len(df_hoso)
        if col_act1.checkbox("☑️ Chọn tất cả danh sách", value=all_selected):
            st.session_state.selected_ids = df_hoso.index.tolist()
        
        selected_df = df_hoso.loc[st.session_state.selected_ids] if st.session_state.selected_ids else pd.DataFrame()
        output = io.BytesIO()
        try:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                selected_df.to_excel(writer, index=False, sheet_name='HoSo_BHXH')
        except Exception:
            csv_data = selected_df.to_csv(index=False).encode('utf-8-sig')
            output = io.BytesIO(csv_data)

        excel_data = output.getvalue()
        
        col_act2.download_button(
            label=f"📥 Xuất Excel ({len(selected_df)} đã chọn)",
            data=excel_data,
            file_name=f"Thong_Ke_Ho_So_BHXH_{date.today().strftime('%d%m%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=(len(selected_df) == 0),
            use_container_width=True
        )

        show_batch_print = col_act3.button(f"🖨️ In Phong bì B5 Hàng loạt ({len(selected_df)} bản)", type="primary", disabled=(len(selected_df) == 0), use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        
        header_cols = st.columns([0.5, 0.6, 1.2, 2.8, 2.8, 1.5, 1.2, 1.4])
        header_cols[0].markdown("**Chọn**")
        header_cols[1].markdown("**STT**")
        header_cols[2].markdown("**Mã ĐV**")
        header_cols[3].markdown("**Tên đơn vị**")
        header_cols[4].markdown("**Địa chỉ**")
        header_cols[5].markdown("**Số hiệu bưu gửi**")
        header_cols[6].markdown("**Ngày nhận gửi**")
        header_cols[7].markdown("**Thao tác**")
        st.markdown("<hr style='margin: 4px 0 12px 0;'>", unsafe_allow_html=True)

        if "preview_print_id" not in st.session_state:
            st.session_state.preview_print_id = None

        for idx, row in df_hoso.reset_index(drop=True).iterrows():
            with st.container():
                cols = st.columns([0.5, 0.6, 1.2, 2.8, 2.8, 1.5, 1.2, 1.4])
                
                is_checked = idx in st.session_state.selected_ids
                if cols[0].checkbox("", value=is_checked, key=f"chk_{idx}"):
                    if idx not in st.session_state.selected_ids:
                        st.session_state.selected_ids.append(idx)
                else:
                    if idx in st.session_state.selected_ids:
                        st.session_state.selected_ids.remove(idx)

                cols[1].write(f"**{idx + 1}**")
                cols[2].write(f"`{row.get('madv') or 'N/A'}`")
                cols[3].write(f"**{row.get('tendv') or ''}**")
                cols[4].write(row.get('diachidv') or '')
                cols[5].write(f"📦 `{row.get('sohieu') or ''}`")
                
                ngay_str = str(row.get('ngaynhan_date') or '')
                cols[6].write(ngay_str)

                btn_col1, btn_col2, btn_col3 = cols[7].columns(3)
                
                if btn_col1.button("🖨️", key=f"btn_p_{idx}", help="In phong bì B5"):
                    st.session_state.preview_print_id = idx

                if btn_col2.button("✏️", key=f"btn_e_{idx}", help="Chỉnh sửa hồ sơ"):
                    edit_hoso_dialog(row)

                if btn_col3.button("🗑️", key=f"btn_d_{idx}", help="Xóa hồ sơ"):
                    conn = get_db_connection()
                    try:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM hoso WHERE id = %s;", (row['id'],))
                        conn.commit()
                        cursor.close()
                        st.cache_data.clear()
                        st.success(f"🗑️ Đã xóa hồ sơ: {row.get('sohieu')}")
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Lỗi khi xóa: {e}")

                if st.session_state.preview_print_id == idx:
                    with st.expander(f"🖨️ Xem trước Phong bì B5: {row.get('tendv')}", expanded=True):
                        try:
                            st.html(render_envelope_html(row))
                        except AttributeError:
                            st.markdown(render_envelope_html(row), unsafe_allow_html=True)

        if show_batch_print and len(selected_df) > 0:
            st.markdown("---")
            st.subheader(f"🖨️ Danh sách Phong bì B5 Hàng loạt ({len(selected_df)} bản in)")
            st.caption("Nhấn Ctrl + P để gửi lệnh in trực tiếp ra máy in.")

            st.markdown("""
            <style>
            @media print {
                @page { size: 235mm 165mm landscape; margin: 0; }
                .b5-envelope { page-break-after: always; }
            }
            </style>
            """, unsafe_allow_html=True)

            for _, hs in selected_df.iterrows():
                try:
                    st.html(render_envelope_html(hs))
                except AttributeError:
                    st.markdown(render_envelope_html(hs), unsafe_allow_html=True)
    else:
        st.info("Không tìm thấy hồ sơ phù hợp với điều kiện thống kê.")

# =========================================================
# TAB 3: CẬP NHẬT THU HỒI MẪU 05
# =========================================================
with tab3:
    with st.container(border=True):
        st.subheader("🔄 Cập nhật Thu hồi Mẫu 05 / Trạng thái phát")
        
        df_hoso_tab3 = load_hoso_data()
        
        if not df_hoso_tab3.empty:
            hs_options = {f"[{r['madv'] or 'N/A'}] {r['tendv']} - Số hiệu: {r['sohieu']}": r for _, r in df_hoso_tab3.iterrows()}
            selected_hs_update_key = st.selectbox("Chọn Hồ sơ cần cập nhật trạng thái:", list(hs_options.keys()))
            
            current_hs = hs_options[selected_hs_update_key]
            
            with st.form("update_status_form"):
                status_list = ["Chưa phát", "Đã phát thành công", "Đã thu hồi Mẫu 05", "Chuyển hoàn", "Khác"]
                default_idx = status_list.index(current_hs['trangthaiphat']) if current_hs['trangthaiphat'] in status_list else 0
                
                new_status = st.selectbox("Trạng thái phát / Thu hồi Mẫu 05:", status_list, index=default_idx)
                new_note = st.text_area("Ghi chú thêm:", value=current_hs['ghichu'] if pd.notna(current_hs['ghichu']) else "")
                
                submit_update = st.form_submit_button("🔄 Cập nhật Trạng Thái", type="primary", use_container_width=True)
                
                if submit_update:
                    conn = get_db_connection()
                    try:
                        cursor = conn.cursor()
                        update_query = "UPDATE hoso SET trangthaiphat = %s, ghichu = %s WHERE id = %s;"
                        cursor.execute(update_query, (new_status, new_note, current_hs['id']))
                        conn.commit()
                        cursor.close()
                        st.cache_data.clear()
                        st.success(f"✅ Đã cập nhật trạng thái cho bưu gửi **{current_hs['sohieu']}** thành: **{new_status}**")
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Lỗi khi cập nhật trạng thái: {e}")