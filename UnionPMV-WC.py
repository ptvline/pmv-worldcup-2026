import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import requests
from streamlit_gsheets import GSheetsConnection

# Cấu hình trang hiển thị
st.set_page_config(page_title="Mini Game World Cup 2026 - PMV", page_icon="⚽", layout="wide")

FILE_NHAN_VIEN = "2026.06 - PMV.csv"
FILE_48_DOI = "danhsach48doi.csv"
PASSWORD_ADMIN = "PMV2026"  # Mật khẩu truy cập menu Admin

# ==============================================================================
# 🔴 ANH ĐIỀN THÔNG TIN 2 ĐƯỜNG LINK CỦA ANH VÀO ĐÂY:
URL_GOOGLE_SHEET = "https://docs.google.com/spreadsheets/d/1JGIDQqRF0yO-1pJ5Vndz4UAUC8JPJDTHoVDR28z6-G0/edit?usp=sharing"
URL_API_SCRIPT = "https://script.google.com/macros/s/AKfycbwfj_HaVX5AM_Whui-sG7VvkotZjpkmeprZBDA2_EED5jNOmKAzSg3Gl-nGPkmn9xCNMg/exec"
# ==============================================================================

# Kết nối đọc dữ liệu công khai công suất cao
conn = st.connection("gsheets", type=GSheetsConnection)

def tai_phieu_bau_cloud():
    try:
        df = conn.read(spreadsheet=URL_GOOGLE_SHEET, worksheet="phieu_bau", ttl=2)
        df.columns = [col.strip() for col in df.columns]
        return df
    except:
        return pd.DataFrame(columns=["Timestamp", "Ma_NV", "Ho_Ten", "Bo_Phan", "Loai_Du_Doan", "Ma_Tran_Hoac_Doi_Voi", "Du_Doan", "Phut_Nop_Som"])

def tai_tran_dau_cloud():
    try:
        df = conn.read(spreadsheet=URL_GOOGLE_SHEET, worksheet="tran_dau", ttl=2)
        df.columns = [col.strip() for col in df.columns]
        if 'Ma_Tran' in df.columns:
            df['Ma_Tran'] = df['Ma_Tran'].astype(str).str.strip()
        return df
    except:
        return pd.DataFrame(columns=["Ma_Tran", "Doi_Left", "Doi_Right", "Thoi_Gian_Mo_Form", "Thoi_Gian_Khoa_Form", "Ket_Qua_Thuc_Te"])

@st.cache_data(ttl=60)
def tai_danh_sach_nhan_viên():
    if os.path.exists(FILE_NHAN_VIEN):
        df = pd.read_csv(FILE_NHAN_VIEN, sep=None, engine='python', encoding="utf-8-sig")
        df.columns = [col.strip() for col in df.columns]
        col_ma = df.columns[0]
        df[col_ma] = df[col_ma].astype(str).str.strip()
        return df
    return pd.DataFrame()

def tai_danh_sach_48_doi():
    if os.path.exists(FILE_48_DOI):
        df = pd.read_csv(FILE_48_DOI, sep=None, engine='python', encoding="utf-8-sig")
        df.columns = [col.strip() for col in df.columns]
        return df
    return pd.DataFrame()

df_nv = tai_danh_sach_nhan_viên()
df_tran = tai_tran_dau_cloud()
df_48_doi = tai_danh_sach_48_doi()

# --- CHIA MENU CHỨC NĂNG ---
menu = st.sidebar.radio("DANH MỤC CHỨC NĂNG", ["⚽ Dự Đoán Trận Đấu", "📊 Bảng Xếp Hạng (Leaderboard)", "🛠️ Quản Trị (Admin)"])

if "ma_nv_ghi_nho" not in st.session_state:
    st.session_state["ma_nv_ghi_nho"] = ""

# ==========================================
# MENU 1: DỰ ĐOÁN (DÀNH CHO NHÂN VIÊN)
# ==========================================
if menu == "⚽ Dự Đoán Trận Đấu":
    st.title("⚽ MINI GAME DỰ ĐOÁN WORLD CUP 2026")
    st.subheader("CÔNG ĐOÀN CÔNG TY TNHH PALFINGER MARINE VIETNAM")
    st.markdown("---")
    
    st.header("I. Thông tin thành viên")
    ma_nv_input = st.text_input("Nhập chính xác Mã nhân viên của bạn:", value=st.session_state["ma_nv_ghi_nho"]).strip()
    
    hop_le = False
    ho_ten, bo_phan, ma_nv_selected = "", "", ""
    
    if ma_nv_input != "":
        if not df_nv.empty:
            col_ma_nv = df_nv.columns[0]
            col_ten_nv = df_nv.columns[1] if len(df_nv.columns) > 1 else col_ma_nv
            col_bophan = df_nv.columns[2] if len(df_nv.columns) > 2 else col_ma_nv
            
            khop_nv = df_nv[df_nv[col_ma_nv] == ma_nv_input]
            
            if not khop_nv.empty:
                thong_tin_nv = khop_nv.iloc[0]
                ho_ten = thong_tin_nv[col_ten_nv]
                bo_phan = thong_tin_nv[col_bophan]
                ma_nv_selected = ma_nv_input
                st.session_state["ma_nv_ghi_nho"] = ma_nv_input
                st.success(f"🔓 **Họ và tên:** {ho_ten}  |  **Bộ phận:** {bo_phan}")
                hop_le = True
            else:
                st.error("❌ Mã nhân viên không tồn tại trong hệ thống của PMV! Vui lòng nhập lại.")
        else:
            st.error("Không tìm thấy file dữ liệu nhân viên để đối chiếu.")
    else:
        st.info("👋 Vui lòng nhập Mã nhân viên để bắt đầu mở cổng bình chọn.")

    if hop_le:
        df_phieu_hien_tai = tai_phieu_bau_cloud()
        df_phieu_hien_tai["Ma_NV"] = df_phieu_hien_tai["Ma_NV"].astype(str).str.strip()
        thoi_gian_hien_tai = datetime.now() + timedelta(hours=7)        
        st.markdown("---")
        st.header("II. Dự đoán Nhà vô địch World Cup 2026")
        da_du_doan_vo_dich = df_phieu_hien_tai[(df_phieu_hien_tai["Ma_NV"] == ma_nv_selected) & (df_phieu_hien_tai["Loai_Du_Doan"] == "Vo_Dich")]
        
        if df_tran.empty:
            st.info("Chưa có lịch trận đấu nào mở ra để xác định hạn đóng cổng Vô Địch.")
        else:
            thoi_gian_khoa_vd = pd.to_datetime(df_tran["Thoi_Gian_Khoa_Form"].iloc[0]).to_pydatetime()
            
            if thoi_gian_hien_tai > thoi_gian_khoa_vd:
                if not da_du_doan_vo_dich.empty:
                    st.success(f"🔒 Hệ thống đã đóng cổng. Dự đoán Đội vô địch cố định của bạn là: **{da_du_doan_vo_dich['Du_Doan'].iloc[0]}**")
                else:
                    st.error("⏳ Đã quá hạn dự đoán Đội vô địch (Cổng đã đóng từ khi vòng đấu bắt đầu).")
            else:
                if not da_du_doan_vo_dich.empty:
                    st.info(f"💡 Bạn đã dự đoán: **{da_du_doan_vo_dich['Du_Doan'].iloc[0]}**. Bạn vẫn có thể chọn đội khác dưới đây và lưu lại trước giờ đóng cổng.")
                
                if not df_48_doi.empty and "Team" in df_48_doi.columns:
                    doi_vo_dich = st.selectbox("Chọn đội tuyển bạn dự đoán sẽ Vô địch:", ["-- Chọn Đội Tuyển --"] + df_48_doi["Team"].dropna().tolist())
                else:
                    doi_vo_dich = st.text_input("Nhập tên đội tuyển bạn dự đoán sẽ Vô địch:")
                
                if st.button("Xác nhận Đội vô địch"):
                    if doi_vo_dich in ["-- Chọn Đội Tuyển --", ""]:
                        st.error("Vui lòng chọn hoặc điền tên một đội tuyển!")
                    else:
                        phut_som_vd = int((thoi_gian_khoa_vd - thoi_gian_hien_tai).total_seconds() / 60)
                        payload = {
                            "action": "save_vote", "worksheet": "phieu_bau",
                            "Timestamp": thoi_gian_hien_tai.strftime("%Y-%m-%d %H:%M:%S"),
                            "Ma_NV": ma_nv_selected, "Ho_Ten": ho_ten, "Bo_Phan": bo_phan,
                            "Loai_Du_Doan": "Vo_Dich", "Ma_Tran_Hoac_Doi_Voi": "Chung_Cuoc",
                            "Du_Doan": doi_vo_dich, "Phut_Nop_Som": phut_som_vd
                        }
                        res = requests.post(URL_API_SCRIPT, data=payload)
                        if "Success" in res.text:
                            st.success(f"🎉 Ghi nhận/Cập nhật thành công Đội vô địch: {doi_vo_dich}")
                            st.rerun()
                        else:
                            st.error("Lỗi đồng bộ Cloud: " + res.text)

        st.markdown("---")
        st.header("III. Dự đoán kết quả trận đấu (Vòng 1/32)")
        
        if df_tran.empty:
            st.info("Hiện tại chưa có trận đấu nào được Admin kích hoạt mở cổng dự đoán.")
        else:
            for index, row in df_tran.iterrows():
                ma_tran = str(row.get("Ma_Tran", index)).strip()
                doi_left = row.get("Doi_Left", "Đội A")
                doi_right = row.get("Doi_Right", "Đội B")
                
                mo_form = pd.to_datetime(row.get("Thoi_Gian_Mo_Form"), format="%Y-%m-%d %H:%M:%S", errors='coerce').to_pydatetime()
                han_khoa = pd.to_datetime(row.get("Thoi_Gian_Khoa_Form"), format="%Y-%m-%d %H:%M:%S", errors='coerce').to_pydatetime()
                
                if thoi_gian_hien_tai >= mo_form:
                    st.markdown(f"#### ⚽ Trận {ma_tran}: {doi_left} vs {doi_right}")
                    da_du_doan_tran = df_phieu_hien_tai[(df_phieu_hien_tai["Ma_NV"] == ma_nv_selected) & (df_phieu_hien_tai["Ma_Tran_Hoac_Doi_Voi"].astype(str) == ma_tran)]
                    
                    if thoi_gian_hien_tai > han_khoa:
                        if not da_du_doan_tran.empty:
                            st.info(f"🔒 Đã đóng cổng. Lựa chọn chính thức của bạn: **{doi_left} [{da_du_doan_tran['Du_Doan'].iloc[0]}] {doi_right}**")
                        else:
                            st.error(f"❌ Trận đấu đã khóa cổng bình chọn vào lúc {han_khoa.strftime('%H:%M %d/%m')} (Hết hiệp 1) và bạn chưa tham gia.")
                    else:
                        if not da_du_doan_tran.empty:
                            st.success(f"✅ Bạn đang chọn: **{doi_left} [{da_du_doan_tran['Du_Doan'].iloc[0]}] {doi_right}**. (Bạn vẫn có thể tích chọn lại và ấn Gửi).")
                        else:
                            st.caption(f"⏳ Cổng đang mở $\rightarrow$ Hạn cuối thay đổi: {han_khoa.strftime('%H:%M %d/%m/%Y')}")
                        
                        lua_chon = st.radio(f"Lựa chọn kết quả của **{doi_left}**:", ["Thắng", "Hòa", "Thua"], key=f"radio_{ma_tran}", index=None, horizontal=True)
                        
                        if lua_chon:
                            with st.popover(f"🚀 Gửi / Cập nhật dự đoán trận {ma_tran}"):
                                st.warning(f"Bạn chọn: {doi_left} [{lua_chon}] {doi_right}?")
                                if st.button("Xác nhận gửi lựa chọn này!", key=f"confirm_{ma_tran}"):
                                    phut_som_tran = int((han_khoa - thoi_gian_hien_tai).total_seconds() / 60)
                                    payload_tran = {
                                        "action": "save_vote", "worksheet": "phieu_bau",
                                        "Timestamp": thoi_gian_hien_tai.strftime("%Y-%m-%d %H:%M:%S"),
                                        "Ma_NV": ma_nv_selected, "Ho_Ten": ho_ten, "Bo_Phan": bo_phan,
                                        "Loai_Du_Doan": "Tran_Dau", "Ma_Tran_Hoac_Doi_Voi": ma_tran,
                                        "Du_Doan": lua_chon, "Phut_Nop_Som": phut_som_tran
                                    }
                                    res_t = requests.post(URL_API_SCRIPT, data=payload_tran)
                                    if "Success" in res_t.text:
                                        st.success("Cập nhật phiếu bầu thành công!")
                                        st.rerun()
                                    else:
                                        st.error("Lỗi: " + res_t.text)
                    st.markdown("---")

# ==========================================
# MENU 2: LEADERBOARD (BẢNG XẾP HẠNG)
# ==========================================
elif menu == "📊 Bảng Xếp Hạng (Leaderboard)":
    st.title("📊 BẢNG TỔNG SOÁT KẾT QUẢ MINI GAME")
    st.markdown("---")
    
    df_phieu = tai_phieu_bau_cloud()
    
    st.header("🏆 1. Bảng Tổng Điểm Dự Đoán Trận Đấu (Vòng 1/32)")
    st.caption("Tiêu chí sắp xếp: Tổng điểm cao nhất (3đ/trận đúng) $\rightarrow$ Tổng số phút nộp sớm nhất của các trận đoán đúng.")
    
    if df_tran.empty or df_phieu.empty or df_phieu[df_phieu['Loai_Du_Doan'] == 'Tran_Dau'].empty:
        st.info("Chưa có đủ dữ liệu trận đấu hoặc phiếu bầu trận đấu trên Cloud để kết xuất bảng tính điểm.")
    else:
        dict_ket_qua = dict(zip(df_tran['Ma_Tran'].astype(str), df_tran['Ket_Qua_Thuc_Te']))
        df_du_doan_tran = df_phieu[df_phieu['Loai_Du_Doan'] == 'Tran_Dau'].copy()
        df_du_doan_tran['Ma_Tran_Hoac_Doi_Voi'] = df_du_doan_tran['Ma_Tran_Hoac_Doi_Voi'].astype(str)
        df_du_doan_tran['Ket_Qua_Thuc_Te'] = df_du_doan_tran['Ma_Tran_Hoac_Doi_Voi'].map(dict_ket_qua)
        
        df_du_doan_tran['Diem'] = df_du_doan_tran.apply(lambda r: 3 if r['Du_Doan'] == r['Ket_Qua_Thuc_Te'] else 0, axis=1)
        df_du_doan_tran['Phut_Som_Hop_Le'] = df_du_doan_tran.apply(lambda r: int(r['Phut_Nop_Som']) if r['Diem'] == 3 else 0, axis=1)
        
        bxh_diem = df_du_doan_tran.groupby(['Ma_NV', 'Ho_Ten', 'Bo_Phan']).agg(
            Tong_Diem=('Diem', 'sum'),
            Tong_Phut_Som=('Phut_Som_Hop_Le', 'sum')
        ).reset_index()
        
        bxh_diem = bxh_diem.sort_values(by=['Tong_Diem', 'Tong_Phut_Som'], ascending=[False, False]).reset_index(drop=True)
        bxh_diem.index += 1
        
        st.dataframe(bxh_diem.rename(columns={
            'Ma_NV': 'Mã Nhân Viên', 'Ho_Ten': 'Họ và Tên', 'Bo_Phan': 'Bộ Phận',
            'Tong_Diem': 'Tổng Điểm', 'Tong_Phut_Som': 'Tổng Phút Sớm (Các Trận Đúng)'
        }), use_container_width=True)
        
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("---")
    
    st.header("🔮 2. Danh Sách Lựa Chọn Đội Vô Địch World Cup 2026")
    df_vd_only = df_phieu[df_phieu['Loai_Du_Doan'] == 'Vo_Dich'].copy()
    
    if df_vd_only.empty:
        st.info("Chưa có thành viên nào thực hiện dự đoán Đội vô địch chung cuộc.")
    else:
        df_vd_show = df_vd_only[['Ma_NV', 'Ho_Ten', 'Bo_Phan', 'Du_Doan', 'Timestamp']].reset_index(drop=True)
        df_vd_show.index += 1
        st.dataframe(df_vd_show.rename(columns={
            'Ma_NV': 'Mã Nhân Viên', 'Ho_Ten': 'Họ và Tên', 'Bo_Phan': 'Bộ Phận',
            'Du_Doan': 'Đội Tuyển Lựa Chọn', 'Timestamp': 'Thời Điểm Thay Đổi Cuối'
        }), use_container_width=True)

# ==========================================
# MENU 3: ADMIN (ĐÃ SỬA CHẠY QUA API WEB APPS SCRIPT)
# ==========================================
elif menu == "🛠️ Quản Trị (Admin)":
    st.title("🛠️ HỆ THỐNG QUẢN TRỊ & NẠP TRẬN ĐẤU (CLOUD API)")
    
    mat_khau = st.text_input("Vui lòng nhập mã bảo mật Admin:", type="password")
    if mat_khau == PASSWORD_ADMIN:
        st.success("Xác thực quyền Quản trị thành công!")
        st.markdown("---")
        
        tab1, tab2 = st.tabs(["➕ Thêm Trận Đấu Mới", "✏️ Cập Nhật Kết Quả Trận Đấu"])
        
        with tab1:
            st.header("Nạp Trận Đấu Mới Vào Hệ Thống")
            ma_tran_moi = st.text_input("Mã Trận (Ví dụ: 32_01):")
            doi1 = st.text_input("Đội tuyển 1 (Bên trái):")
            doi2 = st.text_input("Đội tuyển 2 (Bên phải):")
            
            ngay_da = st.date_input("Chọn ngày thi đấu:", datetime.now() + timedelta(hours=7))
            gio_da = st.time_input("Chọn giờ đá chính thức:", datetime.strptime("18:00", "%H:%M").time())
            
            dt_da = datetime.combine(ngay_da, gio_da)
            dt_mo_tudong = datetime.combine(ngay_da, datetime.strptime("10:00", "%H:%M").time())
            dt_khoa_tudong = dt_da + timedelta(minutes=45)
            
            if st.button("Lưu Trận Đấu"):
                if ma_tran_moi.strip() == "" or doi1.strip() == "" or doi2.strip() == "":
                    st.error("Vui lòng nhập đầy đủ thông tin trận đấu!")
                else:
                    payload_add = {
                        "action": "add_match", "worksheet": "tran_dau",
                        "Ma_Tran": ma_tran_moi.strip(), "Doi_Left": doi1.strip(), "Doi_Right": doi2.strip(),
                        "Thoi_Gian_Mo_Form": dt_mo_tudong.strftime("%Y-%m-%d %H:%M:%S"),
                        "Thoi_Gian_Khoa_Form": dt_khoa_tudong.strftime("%Y-%m-%d %H:%M:%S"),
                        "Ket_Qua_Thuc_Te": "Chưa đá"
                    }
                    res_a = requests.post(URL_API_SCRIPT, data=payload_add)
                    if "Success" in res_a.text:
                        st.success("Đã nạp trận đấu thành công qua API!")
                        st.rerun()
                    else:
                        st.error("Lỗi nạp trận: " + res_a.text)
                        
        with tab2:
            st.header("Cập nhật kết quả sau trận đấu")
            df_cap_nhat = tai_tran_dau_cloud()
            
            if df_cap_nhat.empty:
                st.info("Chưa có trận đấu nào được lưu.")
            else:
                list_tran_chua_update = df_cap_nhat['Ma_Tran'].dropna().tolist()
                tran_selected = st.selectbox("Chọn Mã trận muốn cập nhật kết quả:", list_tran_chua_update)
                
                thong_tin_t = df_cap_nhat[df_cap_nhat['Ma_Tran'] == tran_selected].iloc[0]
                st.write(f"Trận đang chọn: **{thong_tin_t['Doi_Left']} vs {thong_tin_t['Doi_Right']}**")
                
                kq_moi = st.selectbox(f"Kết quả thực tế cho đội **{thong_tin_t['Doi_Left']}**:", ["Chưa đá", "Thắng", "Hòa", "Thua"])
                
                if st.button("Xác nhận cập nhật tỷ số"):
                    payload_update = {
                        "action": "update_result", "worksheet": "tran_dau",
                        "Ma_Tran": tran_selected, "Ket_Qua_Thuc_Te": kq_moi
                    }
                    res_u = requests.post(URL_API_SCRIPT, data=payload_update)
                    if "Success" in res_u.text:
                        st.success("Đã cập nhật kết quả trận đấu lên Cloud qua API thành công!")
                        st.rerun()
                    else:
                        st.error("Lỗi cập nhật tỷ số: " + res_u.text)
    elif mat_khau != "":
        st.error("Sai mã bảo mật Quản trị!")
