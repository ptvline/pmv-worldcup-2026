import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import requests

# Cấu hình trang hiển thị
st.set_page_config(page_title="Mini Game World Cup 2026 - PMV", page_icon="⚽", layout="wide")

FILE_NHAN_VIEN = "2026.06 - PMV.csv"
FILE_48_DOI = "danhsach48doi.csv"
PASSWORD_ADMIN = "PMV2026"  # Mật khẩu truy cập menu Admin

URL_API_SCRIPT = "https://script.google.com/macros/s/AKfycbyjsiiF0DKv8yw8Sf6SWWv49AMVGR6c8UrKFNY5VrctnEZU7letoH-msVsIBZy0cbpZMA/exec"

# --- HÀM TIỆN ÍCH AN TOÀN (TRÁNH CRASH DO DỮ LIỆU LỖI/THIẾU) ---
def an_toan_int(value, default=0):
    """Chuyển giá trị về int một cách an toàn, không bao giờ crash app."""
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default

def co_du_cot(df, danh_sach_cot):
    """Kiểm tra DataFrame có đủ các cột cần thiết trước khi xử lý, tránh KeyError."""
    if df is None or df.empty:
        return False
    return all(c in df.columns for c in danh_sach_cot)

# --- CÁC HÀM TẢI DỮ LIỆU TỪ CLOUD ---
def tai_phieu_bau_cloud():
    # Định nghĩa sẵn danh sách các cột bắt buộc phải có
    cac_cot_mac_dinh = ["Timestamp", "Ma_NV", "Ho_Ten", "Bo_Phan", "Loai_Du_Doan", "Ma_Tran_Hoac_Doi_Voi", "Du_Doan", "Phut_Nop_Som", "Thiet_Bi"]
    try:
        url = f"{URL_API_SCRIPT}?worksheet=phieu_bau"
        response = requests.get(url, timeout=8)
        if response.status_code != 200:
            return pd.DataFrame(columns=cac_cot_mac_dinh)

        data = response.json()

        # Kiểm tra nếu có dữ liệu trả về từ API VÀ đúng định dạng list (tránh lỗi nếu API trả về dict/lỗi)
        if isinstance(data, list) and len(data) > 0:
            df = pd.DataFrame(data)
            df.columns = [str(col).strip() for col in df.columns]
            if 'Ma_NV' in df.columns:
                df['Ma_NV'] = df['Ma_NV'].astype(str).str.strip()
            # Đảm bảo luôn có đủ các cột bắt buộc, nếu thiếu thì bổ sung cột trống
            for cot in cac_cot_mac_dinh:
                if cot not in df.columns:
                    df[cot] = ""
            return df
        else:
            # Nếu Sheet trống (chưa có ai vote) hoặc dữ liệu không hợp lệ, trả về DataFrame trống NHƯNG PHẢI CÓ ĐỦ CỘT
            return pd.DataFrame(columns=cac_cot_mac_dinh)
    except Exception:
        # Nếu lỗi kết nối mạng hoặc lỗi API, trả về cấu trúc cột mặc định để app không bị crash
        return pd.DataFrame(columns=cac_cot_mac_dinh)
        
def tai_tran_dau_cloud():
    cac_cot_tran = ["Ma_Tran", "Doi_Left", "Doi_Right", "Thoi_Gian_Mo_Form", "Thoi_Gian_Khoa_Form", "Ket_Qua_Thuc_Te", "Active"]
    try:
        url = f"{URL_API_SCRIPT}?worksheet=tran_dau"
        response = requests.get(url, timeout=8)
        if response.status_code != 200:
            return pd.DataFrame(columns=cac_cot_tran)

        data = response.json()
        if not isinstance(data, list) or len(data) == 0:
            return pd.DataFrame(columns=cac_cot_tran)

        df = pd.DataFrame(data)
        if not df.empty:
            df.columns = [str(col).strip() for col in df.columns]
            if 'Ma_Tran' in df.columns:
                df['Ma_Tran'] = df['Ma_Tran'].astype(str).str.strip()
        return df
    except Exception:
        return pd.DataFrame(columns=cac_cot_tran)

@st.cache_data(ttl=60)
def tai_danh_sach_nhan_vien():
    if os.path.exists(FILE_NHAN_VIEN):
        try:
            df = pd.read_csv(FILE_NHAN_VIEN, sep=None, engine='python', encoding="utf-8-sig")
            df.columns = [col.strip() for col in df.columns]
            if df.empty or len(df.columns) == 0:
                return pd.DataFrame()
            col_ma = df.columns[0]
            df[col_ma] = df[col_ma].astype(str).str.strip()
            return df
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

@st.cache_data(ttl=300)
def tai_danh_sach_48_doi():
    if os.path.exists(FILE_48_DOI):
        try:
            df = pd.read_csv(FILE_48_DOI, sep=None, engine='python', encoding="utf-8-sig")
            df.columns = [col.strip() for col in df.columns]
            return df
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

# Tải dữ liệu danh mục tĩnh ban đầu
df_nv = tai_danh_sach_nhan_vien()
df_tran = tai_tran_dau_cloud()
df_48_doi = tai_danh_sach_48_doi()

# --- KHỞI TẠO BỘ NHỚ TẠM (SESSION STATE) ĐỂ TĂNG TỐC ĐỘ ---
if "ma_nv_ghi_nho" not in st.session_state:
    st.session_state["ma_nv_ghi_nho"] = ""

if "df_phieu_cache" not in st.session_state:
    st.session_state["df_phieu_cache"] = None

# --- CHIA MENU CHỨC NĂNG ---
menu = st.sidebar.radio("DANH MỤC CHỨC NĂNG", ["⚽ Dự Đoán Trận Đấu", "📊 Bảng Xếp Hạng (Leaderboard)", "🛠️ Quản Trị (Admin)"])

# Lấy thông tin đặc trưng trình duyệt để nhận diện thiết bị (Chống vote hộ)
thong_tin_may_tinh = st.context.headers.get("User-Agent", "Unknown_Browser")

# ==========================================
# MENU 1: DỰ ĐOÁN (NHÂN VIÊN)
# ==========================================
if menu == "⚽ Dự Đoán Trận Đấu":
    st.title("⚽ MINI GAME DỰ ĐOÁN WORLD CUP 2026")
    st.subheader("CÔNG ĐOÀN CÔNG TY TNHH PALFINGER MARINE VIETNAM")
    st.markdown("---")
    
    st.header("I. Thông tin thành viên")
    ma_nv_input = st.text_input("Nhập chính xác Mã nhân viên của bạn:", value=st.session_state["ma_nv_ghi_nho"]).strip()
    
    hop_le = False
    ho_ten, bo_phan, ma_nv_selected = "", "", ""
    
    # Kiểm tra mã nhân viên đăng nhập
    if ma_nv_input != "":
        if not df_nv.empty:
            if len(df_nv.columns) < 3:
                st.warning("⚠️ File danh sách nhân viên thiếu cột (cần ít nhất 3 cột: Mã NV, Họ Tên, Bộ Phận). Thông tin hiển thị có thể không chính xác.")
            col_ma_nv = df_nv.columns[0]
            col_ten_nv = df_nv.columns[1] if len(df_nv.columns) > 1 else col_ma_nv
            col_bophan = df_nv.columns[2] if len(df_nv.columns) > 2 else col_ma_nv
            
            khop_nv = df_nv[df_nv[col_ma_nv] == ma_nv_input]
            if not khop_nv.empty:
                thong_tin_nv = khop_nv.iloc[0]
                ho_ten = thong_tin_nv[col_ten_nv]
                bo_phan = thong_tin_nv[col_bophan]
                ma_nv_selected = ma_nv_input
                
                # Nếu đổi mã nhân viên hoặc lần đầu vào, kích hoạt nạp dữ liệu phiếu bầu mới
                if st.session_state["ma_nv_ghi_nho"] != ma_nv_input or st.session_state["df_phieu_cache"] is None:
                    st.session_state["df_phieu_cache"] = tai_phieu_bau_cloud()
                
                st.session_state["ma_nv_ghi_nho"] = ma_nv_input
                df_phieu_hien_tai = st.session_state["df_phieu_cache"]
                
                st.success(f"🔓 **Họ và tên:** {ho_ten}  |  **Bộ phận:** {bo_phan}")
                hop_le = True
            else:
                st.error("❌ Mã nhân viên không tồn tại trong hệ thống của PMV! Vui lòng kiểm tra lại.")
        else:
            st.error("Không tìm thấy file dữ liệu nhân viên để đối chiếu.")
    else:
        st.info("👋 Vui lòng nhập Mã nhân viên để bắt đầu mở cổng bình chọn.")

    if hop_le:
        thoi_gian_hien_tai = datetime.now() + timedelta(hours=7)
        
        # --- II. DỰ ĐOÁN NHÀ VÔ ĐỊCH ---
        st.markdown("---")
        st.header("II. Dự đoán Nhà vô địch World Cup 2026")
        
        da_du_doan_vo_dich = pd.DataFrame()
        if co_du_cot(df_phieu_hien_tai, ["Ma_NV", "Loai_Du_Doan", "Du_Doan"]):
            df_phieu_hien_tai["Ma_NV"] = df_phieu_hien_tai["Ma_NV"].astype(str).str.strip()
            da_du_doan_vo_dich = df_phieu_hien_tai[(df_phieu_hien_tai["Ma_NV"] == ma_nv_selected) & (df_phieu_hien_tai["Loai_Du_Doan"] == "Vo_Dich")]
        
        # Đóng cổng cố định 03:00 sáng ngày 20/07/2026
        thoi_gian_khoa_vd = datetime.strptime("2026-07-20 03:00:00", "%Y-%m-%d %H:%M:%S")
        
        if thoi_gian_hien_tai > thoi_gian_khoa_vd:
            if not da_du_doan_vo_dich.empty:
                st.success(f"🔒 Hệ thống đã đóng cổng. Dự đoán Đội vô địch cố định của bạn là: **{da_du_doan_vo_dich['Du_Doan'].iloc[0]}**")
            else:
                st.error("⏳ Đã quá hạn dự đoán Đội vô địch (Cổng đã đóng vào lúc 03:00 ngày 20/07/2026).")
        else:
            if not da_du_doan_vo_dich.empty:
                st.info(f"💡 Bạn đã dự đoán: **{da_du_doan_vo_dich['Du_Doan'].iloc[0]}**. Bạn vẫn có thể cập nhật lựa chọn mới trước giờ khóa cổng.")
            
            if not df_48_doi.empty and "Team" in df_48_doi.columns:
                doi_vo_dich = st.selectbox("Chọn đội tuyển bạn dự đoán sẽ Vô địch:", ["-- Chọn Đội Tuyển --"] + df_48_doi["Team"].dropna().tolist())
            else:
                doi_vo_dich = st.text_input("Nhập tên đội tuyển bạn dự đoán sẽ Vô địch:")
            
            if st.button("Xác nhận Đội vô địch"):
                if doi_vo_dich in ["-- Chọn Đội Tuyển --", ""]:
                    st.error("Vui lòng chọn hoặc điền tên một đội tuyển!")
                else:
                    phut_som_vd = int((thoi_gian_khoa_vd - thoi_gian_hien_tai).total_seconds() / 60)
                    payload_vd = {
                        "action": "save_vote", "worksheet": "phieu_bau",
                        "Timestamp": thoi_gian_hien_tai.strftime("%Y-%m-%d %H:%M:%S"),
                        "Ma_NV": ma_nv_selected, "Ho_Ten": ho_ten, "Bo_Phan": bo_phan,
                        "Loai_Du_Doan": "Vo_Dich", "Ma_Tran_Hoac_Doi_Voi": "Chung_Cuoc",
                        "Du_Doan": doi_vo_dich, "Phut_Nop_Som": phut_som_vd,
                        "Thiet_Bi": thong_tin_may_tinh
                    }
                    
                    # Kiểm tra an toàn trước khi tạo mask để tránh KeyError
                    df_cache = st.session_state["df_phieu_cache"]
                    
                    if "Ma_NV" in df_cache.columns and "Loai_Du_Doan" in df_cache.columns:
                        mask_vd = (df_cache["Ma_NV"] == ma_nv_selected) & (df_cache["Loai_Du_Doan"] == "Vo_Dich")
                        if mask_vd.any():
                            st.session_state["df_phieu_cache"].loc[mask_vd, "Du_Doan"] = doi_vo_dich
                            st.session_state["df_phieu_cache"].loc[mask_vd, "Timestamp"] = payload_vd["Timestamp"]
                        else:
                            st.session_state["df_phieu_cache"] = pd.concat([df_cache, pd.DataFrame([payload_vd])], ignore_index=True)
                    else:
                        # Nếu cache chưa có cột (do sheet rỗng), tạo mới luôn một DataFrame từ payload
                        st.session_state["df_phieu_cache"] = pd.DataFrame([payload_vd])

        # --- III. DỰ ĐOÁN KẾT QUẢ TRẬN ĐẤU (VÒNG 1/32) ---
        st.markdown("---")
        st.header("III. Dự đoán kết quả trận đấu (Vòng 1/32)")
        
        if df_tran.empty:
            st.info("Hiện tại chưa có lịch trận đấu nào được kích hoạt trên hệ thống.")
        else:
            df_tran.columns = [c.strip() for c in df_tran.columns]
            
            # Hàm xử lý thời gian an toàn, loại bỏ 100% lỗi so sánh lệch múi giờ
            def ep_kieu_tg_safe(val):
                try:
                    return pd.to_datetime(val).to_pydatetime().replace(tzinfo=None)
                except:
                    return thoi_gian_hien_tai
            
            df_tran['dt_khoa_sort'] = df_tran['Thoi_Gian_Khoa_Form'].apply(ep_kieu_tg_safe)
            
            # ƯU TIÊN ĐƯA CÁC TRẬN SẮP KHÓA FORM LÊN ĐẦU
            df_tran = df_tran.sort_values(by='dt_khoa_sort', ascending=True).reset_index(drop=True)
            
            # Tạo mặc định nếu cột Active chưa tồn tại trên Sheet
            if 'Active' not in df_tran.columns:
                df_tran['Active'] = 'Hiện'
                
            # Phân nhóm Trận đấu theo trạng thái cột Active
            df_dang_mo_hien = df_tran[df_tran['Active'].astype(str).str.strip() != 'Ẩn']
            df_da_gom_an = df_tran[df_tran['Active'].astype(str).str.strip() == 'Ẩn']
            
            # Hàm dựng giao diện từng dòng trận đấu
            def render_giao_dien_tran(row_data, idx_key):
                ma_tran = str(row_data.get("Ma_Tran", idx_key)).strip()
                doi_left = row_data.get("Doi_Left", "Đội A")
                doi_right = row_data.get("Doi_Right", "Đội B")
                han_khoa = ep_kieu_tg_safe(row_data.get("Thoi_Gian_Khoa_Form"))
                
                st.markdown(f"#### ⚽ Trận {ma_tran}: {doi_left} vs {doi_right}")
                
                da_du_doan_tran = pd.DataFrame()
                if co_du_cot(st.session_state["df_phieu_cache"], ["Ma_NV", "Ma_Tran_Hoac_Doi_Voi", "Du_Doan"]):
                    st.session_state["df_phieu_cache"]["Ma_Tran_Hoac_Doi_Voi"] = st.session_state["df_phieu_cache"]["Ma_Tran_Hoac_Doi_Voi"].astype(str).str.strip()
                    da_du_doan_tran = st.session_state["df_phieu_cache"][
                        (st.session_state["df_phieu_cache"]["Ma_NV"] == ma_nv_selected) & 
                        (st.session_state["df_phieu_cache"]["Ma_Tran_Hoac_Doi_Voi"] == ma_tran)
                    ]
                
                # Trường hợp: Trận đấu đã quá hạn khóa cổng
                if thoi_gian_hien_tai > han_khoa:
                    if not da_du_doan_tran.empty:
                        st.info(f"🔒 Đã đóng cổng. Lựa chọn chính thức của bạn: **{doi_left} [{da_du_doan_tran['Du_Doan'].iloc[0]}] {doi_right}**")
                    else:
                        st.error(f"❌ Trận đấu đã đóng cổng bình chọn vào lúc {han_khoa.strftime('%H:%M %d/%m')} (Bạn đã bỏ lỡ).")
                # Trường hợp: Cổng vẫn đang mở để vote / sửa
                else:
                    if not da_du_doan_tran.empty:
                        st.success(f"✅ Bạn đang chọn: **{doi_left} [{da_du_doan_tran['Du_Doan'].iloc[0]}] {doi_right}**. (Bạn vẫn có thể tích chọn lại và gửi đè).")
                    else:
                        st.caption(f"⏳ Cổng đang mở -> Hạn cuối: {han_khoa.strftime('%H:%M %d/%m/%Y')}")
                    
                    lua_chon = st.radio(f"Lựa chọn kết quả của **{doi_left}**:", ["Thắng", "Hòa", "Thua"], key=f"radio_{ma_tran}_{idx_key}", index=None, horizontal=True)
                    
                    if lua_chon:
                        with st.popover(f"🚀 Gửi / Cập nhật dự đoán trận {ma_tran}"):
                            st.warning(f"Xác nhận lựa chọn: {doi_left} [{lua_chon}] {doi_right}?")
                            if st.button("Xác nhận gửi!", key=f"btn_confirm_{ma_tran}_{idx_key}"):
                                phut_som_tran = int((han_khoa - thoi_gian_hien_tai).total_seconds() / 60)
                                payload_tran = {
                                    "action": "save_vote", "worksheet": "phieu_bau",
                                    "Timestamp": thoi_gian_hien_tai.strftime("%Y-%m-%d %H:%M:%S"),
                                    "Ma_NV": ma_nv_selected, "Ho_Ten": ho_ten, "Bo_Phan": bo_phan,
                                    "Loai_Du_Doan": "Tran_Dau", "Ma_Tran_Hoac_Doi_Voi": ma_tran,
                                    "Du_Doan": lua_chon, "Phut_Nop_Som": phut_som_tran,
                                    "Thiet_Bi": thong_tin_may_tinh
                                }
                                
                                # TĂNG TỐC SIÊU TỐC: Ghi trực tiếp vào biến cache trong RAM trước
                                df_c = st.session_state["df_phieu_cache"]
                                mask_t = (df_c["Ma_NV"] == ma_nv_selected) & (df_c["Ma_Tran_Hoac_Doi_Voi"] == ma_tran)
                                
                                if mask_t.any():
                                    df_c.loc[mask_t, "Du_Doan"] = lua_chon
                                    df_c.loc[mask_t, "Timestamp"] = payload_tran["Timestamp"]
                                    df_c.loc[mask_t, "Phut_Nop_Som"] = phut_som_tran
                                else:
                                    st.session_state["df_phieu_cache"] = pd.concat([df_c, pd.DataFrame([payload_tran])], ignore_index=True)
                                
                                # Đẩy dữ liệu lên Cloud chạy ngầm, không bắt giao diện đứng hình chờ đợi
                                try:
                                    requests.post(URL_API_SCRIPT, data=payload_tran, timeout=3)
                                except:
                                    pass
                                
                                st.toast(f"⚽ Đã lưu Trận {ma_tran}: {lua_chon}")
                                st.rerun()
                st.markdown("---")

            # 1. Vẽ cụm trận đang để trạng thái Hiện lên màn hình chính
            if not df_dang_mo_hien.empty:
                for index, row in df_dang_mo_hien.iterrows():
                    render_giao_dien_tran(row, f"hien_{index}")
            else:
                st.info("Không có trận đấu nào được đặt trạng thái 'Hiện'.")
                
            # 2. Vẽ cụm trận đấu đã Ẩn vào nút Expander thu gọn gọn gàng
            if not df_da_gom_an.empty:
                with st.expander("📦 Xem danh sách các trận đấu cũ đã ẩn / lưu trữ"):
                    for index, row in df_da_gom_an.iterrows():
                        render_giao_dien_tran(row, f"an_{index}")

# ==========================================
# MENU 2: LEADERBOARD (BẢNG XẾP HẠNG)
# ==========================================
elif menu == "📊 Bảng Xếp Hạng (Leaderboard)":
    st.title("📊 BẢNG TỔNG SOÁT KẾT QUẢ MINI GAME")
    st.markdown("---")
    
    # Ép buộc tải mới từ Cloud khi xem bảng xếp hạng để đảm bảo điểm số chính xác nhất
    df_phieu = tai_phieu_bau_cloud()
    
    st.header("🏆 1. Bảng Tổng Điểm Dự Đoán Trận Đấu (Vòng 1/32)")
    
    if not co_du_cot(df_tran, ["Ma_Tran", "Ket_Qua_Thuc_Te"]) or not co_du_cot(df_phieu, ["Loai_Du_Doan"]) or df_phieu[df_phieu['Loai_Du_Doan'] == 'Tran_Dau'].empty:
        st.info("Chưa có đủ dữ liệu trên Cloud để phân tích kết quả xếp hạng.")
    else:
        dict_ket_qua = dict(zip(df_tran['Ma_Tran'].astype(str), df_tran['Ket_Qua_Thuc_Te']))
        df_du_doan_tran = df_phieu[df_phieu['Loai_Du_Doan'] == 'Tran_Dau'].copy()
        df_du_doan_tran['Ma_Tran_Hoac_Doi_Voi'] = df_du_doan_tran['Ma_Tran_Hoac_Doi_Voi'].astype(str)
        df_du_doan_tran['Ket_Qua_Thuc_Te'] = df_du_doan_tran['Ma_Tran_Hoac_Doi_Voi'].map(dict_ket_qua)
        
        df_du_doan_tran['Diem'] = df_du_doan_tran.apply(lambda r: 3 if r['Du_Doan'] == r['Ket_Qua_Thuc_Te'] else 0, axis=1)
        df_du_doan_tran['Phut_Som_Hop_Le'] = df_du_doan_tran.apply(lambda r: an_toan_int(r.get('Phut_Nop_Som')) if r['Diem'] == 3 else 0, axis=1)
        
        if not co_du_cot(df_du_doan_tran, ["Ma_NV", "Ho_Ten", "Bo_Phan"]):
            st.warning("⚠️ Dữ liệu phiếu bầu thiếu thông tin Mã NV/Họ tên/Bộ phận, không thể tổng hợp bảng xếp hạng.")
        else:
            bxh_diem = df_du_doan_tran.groupby(['Ma_NV', 'Ho_Ten', 'Bo_Phan']).agg(
                Tong_Diem=('Diem', 'sum'),
                Tong_Phut_Som=('Phut_Som_Hop_Le', 'sum')
            ).reset_index()
            
            bxh_diem = bxh_diem.sort_values(by=['Tong_Diem', 'Tong_Phut_Som'], ascending=[False, False]).reset_index(drop=True)
            bxh_diem.index += 1
            
            st.dataframe(bxh_diem.rename(columns={
                'Ma_NV': 'Mã Nhân Viên', 'Ho_Ten': 'Họ và Tên', 'Bo_Phan': 'Bộ Phận',
                'Tong_Diem': 'Tổng Điểm', 'Tong_Phut_Som': 'Tổng Phút Sớm'
            }), use_container_width=True)
        
    st.markdown("---")
    st.header("🔮 2. Danh Sách Lựa Chọn Đội Vô Địch World Cup 2026")
    df_vd_only = df_phieu[df_phieu['Loai_Du_Doan'] == 'Vo_Dich'].copy() if co_du_cot(df_phieu, ["Loai_Du_Doan"]) else pd.DataFrame()
    
    if df_vd_only.empty:
        st.info("Chưa có thành viên nào thực hiện dự đoán Đội vô địch.")
    else:
        cac_cot_can = ['Ma_NV', 'Ho_Ten', 'Bo_Phan', 'Du_Doan', 'Timestamp']
        df_vd_show = df_vd_only.reindex(columns=cac_cot_can).reset_index(drop=True)
        df_vd_show.index += 1
        st.dataframe(df_vd_show.rename(columns={
            'Ma_NV': 'Mã Nhân Viên', 'Ho_Ten': 'Họ và Tên', 'Bo_Phan': 'Bộ Phận',
            'Du_Doan': 'Đội Tuyển Lựa Chọn', 'Timestamp': 'Thời Điểm Lưu Phiếu'
        }), use_container_width=True)

# ==========================================
# MENU 3: QUẢN TRỊ (ADMIN)
# ==========================================
elif menu == "🛠️ Quản Trị (Admin)":
    st.title("🛠️ HỆ THỐNG QUẢN TRỊ & NẠP TRẬN ĐẤU")
    
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
                    try:
                        res_a = requests.post(URL_API_SCRIPT, data=payload_add, timeout=10)
                        if "Success" in res_a.text:
                            st.success("Đã nạp trận đấu thành công!")
                            st.rerun()
                        else:
                            st.error("Lỗi nạp trận: " + res_a.text)
                    except requests.exceptions.RequestException as e:
                        st.error(f"❌ Không thể kết nối tới Cloud (mạng chậm hoặc API lỗi). Vui lòng thử lại sau. Chi tiết: {e}")
                        
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
                    try:
                        res_u = requests.post(URL_API_SCRIPT, data=payload_update, timeout=10)
                        if "Success" in res_u.text:
                            st.success("Đã cập nhật kết quả thành công!")
                            st.rerun()
                        else:
                            st.error("Lỗi cập nhật tỷ số: " + res_u.text)
                    except requests.exceptions.RequestException as e:
                        st.error(f"❌ Không thể kết nối tới Cloud (mạng chậm hoặc API lỗi). Vui lòng thử lại sau. Chi tiết: {e}")
    elif mat_khau != "":
        st.error("Sai mã bảo mật Quản trị!")
