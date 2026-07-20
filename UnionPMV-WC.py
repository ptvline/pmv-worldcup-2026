import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import re
import unicodedata
import requests

# Cấu hình trang hiển thị
st.set_page_config(page_title="Mini Game World Cup 2026 - PMV", page_icon="⚽", layout="wide")

FILE_NHAN_VIEN = "2026.06 - PMV.csv"
FILE_48_DOI = "danhsach48doi.csv"
PASSWORD_ADMIN = "PMV2026"  # Mật khẩu truy cập menu Admin


URL_API_SCRIPT = "https://script.google.com/macros/s/AKfycbwT-cMsP5MLBWb0ugoR64MODVfZZ5ABYNBFNd6HGKy0UL_y_-cPsGRrlW-TcbyUfxD45w/exec"

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

def chuan_hoa_ma_tran(ma):
    """Chuẩn hóa mã trận dùng để SO KHỚP (không dùng để hiển thị).
    Mục đích: tránh tình trạng phiếu bầu cũ bị "mồ côi" (mất thông tin đã vote,
    mất điểm ở BXH) chỉ vì mã trận khi Admin nạp/nạp lại lệch nhau về:
    - chữ hoa/thường
    - khoảng trắng thừa ở đầu/cuối hoặc ở giữa (vd "4- 01"), kể cả khoảng trắng
      không xuống dòng (non-breaking space) hay các ký tự VÔ HÌNH (zero-width
      space, BOM...) thường dính theo khi copy-paste từ Excel/Google Sheets
    - các loại gạch ngang unicode trông giống nhau (–, —, − vs -)
    - SỐ 0 Ở ĐẦU mỗi cụm số (vd "04-01" so với "4-01" phải được coi là CÙNG 1 trận)
    - các ký tự full-width (vd chữ số kiểu Nhật "４" chuẩn hóa NFKC về "4")
    LƯU Ý: KHÔNG gộp dấu gạch ngang "-" với gạch dưới "_" làm một, vì 2 ký tự này
    đang được dùng để PHÂN BIỆT vòng đấu (vd "16-01" là Vòng 1/16, "16_01" là Vòng 1/8).
    Hàm này KHÔNG thay đổi giá trị Ma_Tran gốc dùng để hiển thị cho người dùng.
    """
    if ma is None:
        return ""
    s = str(ma).strip()
    s = unicodedata.normalize('NFKC', s)  # chuẩn hóa ký tự full-width, tổ hợp Unicode
    s = s.upper()
    for ky_tu_gach in ["–", "—", "−"]:
        s = s.replace(ky_tu_gach, "-")
    # Loại bỏ MỌI ký tự khoảng trắng (kể cả non-breaking space) và các ký tự vô hình
    # thường gặp khi copy dữ liệu từ Excel/Web vào Google Sheets
    s = re.sub(r'[\s\u200b\u200c\u200d\u2060\ufeff\u00ad]+', '', s)
    # Xóa số 0 thừa ở đầu mỗi cụm chữ số liên tiếp (không đụng tới dấu "-"/"_")
    s = re.sub(r'(?<![0-9])0+(?=[0-9])', '', s)
    return s

def chuan_hoa_ma_nv(nv):
    """Chuẩn hóa Mã nhân viên dùng để SO KHỚP. Xử lý trường hợp Google Sheets trả số
    dạng float (vd 419 bị ép kiểu thành "419.0") khiến so khớp với input "419" của
    người dùng bị trượt, đồng thời loại khoảng trắng/ký tự ẩn tương tự mã trận."""
    if nv is None:
        return ""
    s = str(nv).strip()
    s = unicodedata.normalize('NFKC', s)
    s = re.sub(r'[\s\u200b\u200c\u200d\u2060\ufeff\u00ad]+', '', s)
    if re.fullmatch(r'-?\d+\.0+', s):
        s = s.split('.')[0]
    return s

def sinh_cac_khoa_ma_tran(ma):
    """Sinh TẤT CẢ các khóa so khớp khả dĩ cho 1 giá trị mã trận thô.
    LÝ DO: khi cột lưu mã trận trên Google Sheets KHÔNG được định dạng cứng là
    "Văn bản thuần" (Plain Text), Google Sheets sẽ tự động diễn giải các mã trận
    dạng số như "04-04" thành kiểu NGÀY THÁNG (Date) -> giá trị đọc về qua API
    không còn là chuỗi "04-04" nữa mà là một ngày (vd "2026-04-04T00:00:00.000Z",
    "4/4/2026"...). Không phép chuẩn hóa chuỗi thông thường nào sửa được việc này
    vì bản chất KIỂU DỮ LIỆU đã bị đổi hoàn toàn ngay từ trong Sheet.
    Hàm này: nếu giá trị parse được thành ngày tháng hợp lệ, sinh thêm các mã dạng
    "M-D" và "D-M" (thử cả 2 chiều vì không chắc Google hiểu theo thứ tự nào) để
    khôi phục lại đúng trận, bên cạnh khóa chuẩn hóa trực tiếp.
    Trả về: set các khóa (đã qua chuan_hoa_ma_tran).
    """
    ket_qua = {chuan_hoa_ma_tran(ma)}
    if ma is None:
        return ket_qua
    s = str(ma).strip()
    if s == "" or s.lower() == "nan":
        return ket_qua
    try:
        dt = pd.to_datetime(s)
        ket_qua.add(chuan_hoa_ma_tran(f"{dt.month}-{dt.day}"))
        ket_qua.add(chuan_hoa_ma_tran(f"{dt.day}-{dt.month}"))
    except Exception:
        pass
    return ket_qua


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
                # LỌC BỎ CÁC DÒNG "RÁC"/TRỐNG: Google Apps Script đôi khi trả về thêm
                # các dòng trống phía dưới vùng dữ liệu thực (do dropdown/định dạng ở
                # cột Ket_Qua_Thuc_Te kéo dài quá số dòng thực tế). Nếu không lọc, các
                # dòng này sẽ hiện thành "trận ma" (Trận : vs, hạn cuối = giờ hiện tại).
                df = df[(df['Ma_Tran'] != "") & (df['Ma_Tran'].str.lower() != "nan")]
                df = df.reset_index(drop=True)
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

if "thong_bao_loi_luu" not in st.session_state:
    st.session_state["thong_bao_loi_luu"] = None

def kiem_tra_luu_thanh_cong(response_text):
    """Kiểm tra phản hồi từ Apps Script có thực sự lưu thành công hay không.
    Không chỉ dựa vào từ khóa 'Success' đơn thuần vì có thể lẫn trong thông báo lỗi
    (vd JSON trả về chứa cả 'success:false'); kiểm tra chặt hơn bằng cách loại trừ
    các từ khóa lỗi phổ biến."""
    if not response_text:
        return False
    text_lower = str(response_text).strip().lower()
    co_tu_thanh_cong = "success" in text_lower
    co_tu_loi = ("error" in text_lower) or ("lỗi" in text_lower) or ("false" in text_lower)
    return co_tu_thanh_cong and not co_tu_loi

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

        # Hiển thị cảnh báo LƯU THẤT BẠI (nếu có, từ lần bấm "Xác nhận gửi" trước đó) một cách
        # rõ ràng và KHÔNG tự biến mất như st.toast, để nhân viên biết chắc mình cần gửi lại.
        if st.session_state.get("thong_bao_loi_luu"):
            st.error(st.session_state["thong_bao_loi_luu"])
            if st.button("Đã hiểu, ẩn cảnh báo này"):
                st.session_state["thong_bao_loi_luu"] = None
                st.rerun()
        
        # --- II. DỰ ĐOÁN NHÀ VÔ ĐỊCH ---
        st.markdown("---")
        st.header("II. Dự đoán Nhà vô địch World Cup 2026")
        
        da_du_doan_vo_dich = pd.DataFrame()
        if co_du_cot(df_phieu_hien_tai, ["Ma_NV", "Loai_Du_Doan", "Du_Doan"]):
            df_phieu_hien_tai["Ma_NV"] = df_phieu_hien_tai["Ma_NV"].astype(str).str.strip()
            da_du_doan_vo_dich = df_phieu_hien_tai[(df_phieu_hien_tai["Ma_NV"].apply(chuan_hoa_ma_nv) == chuan_hoa_ma_nv(ma_nv_selected)) & (df_phieu_hien_tai["Loai_Du_Doan"] == "Vo_Dich")]
        
        # Đóng cổng cố định 8:45 sáng ngày 04/07/2026
        thoi_gian_khoa_vd = datetime.strptime("2026-07-04 08:45:00", "%Y-%m-%d %H:%M:%S")
        
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

                    # ĐẨY DỮ LIỆU LÊN CLOUD TRƯỚC; chỉ cập nhật cache RAM khi Cloud xác nhận
                    # lưu thành công, để tránh giao diện hiện "đã lưu" trong khi thực tế
                    # Google Sheet chưa hề nhận được (phiếu sẽ biến mất sau khi F5).
                    try:
                        res_vd = requests.post(URL_API_SCRIPT, data=payload_vd, timeout=8)
                        luu_thanh_cong_vd = kiem_tra_luu_thanh_cong(res_vd.text)
                        noi_dung_phan_hoi_vd = res_vd.text
                    except requests.exceptions.RequestException as e:
                        luu_thanh_cong_vd = False
                        noi_dung_phan_hoi_vd = str(e)

                    if luu_thanh_cong_vd:
                        # Kiểm tra an toàn trước khi tạo mask để tránh KeyError
                        df_cache = st.session_state["df_phieu_cache"]

                        if "Ma_NV" in df_cache.columns and "Loai_Du_Doan" in df_cache.columns:
                            mask_vd = (df_cache["Ma_NV"].apply(chuan_hoa_ma_nv) == chuan_hoa_ma_nv(ma_nv_selected)) & (df_cache["Loai_Du_Doan"] == "Vo_Dich")
                            if mask_vd.any():
                                st.session_state["df_phieu_cache"].loc[mask_vd, "Du_Doan"] = doi_vo_dich
                                st.session_state["df_phieu_cache"].loc[mask_vd, "Timestamp"] = payload_vd["Timestamp"]
                            else:
                                st.session_state["df_phieu_cache"] = pd.concat([df_cache, pd.DataFrame([payload_vd])], ignore_index=True)
                        else:
                            # Nếu cache chưa có cột (do sheet rỗng), tạo mới luôn một DataFrame từ payload
                            st.session_state["df_phieu_cache"] = pd.DataFrame([payload_vd])

                        st.session_state["thong_bao_loi_luu"] = None
                        st.toast(f"🏆 Đã lưu dự đoán Đội vô địch: {doi_vo_dich}")
                    else:
                        st.session_state["thong_bao_loi_luu"] = (
                            f"❌ LƯU THẤT BẠI cho dự đoán Đội vô địch ({doi_vo_dich}). Lựa chọn của bạn "
                            f"CHƯA được ghi nhận lên hệ thống, vui lòng chọn lại và bấm 'Xác nhận Đội vô địch' "
                            f"một lần nữa. (Phản hồi từ Cloud: {noi_dung_phan_hoi_vd})"
                        )

                    st.rerun()

        # --- III. DỰ ĐOÁN KẾT QUẢ TRẬN ĐẤU (VÒNG 1/32) ---
        st.markdown("---")
        st.header("III. Dự đoán kết quả trận đấu")
        
        if df_tran.empty:
            st.info("Hiện tại chưa có lịch trận đấu nào được kích hoạt trên hệ thống.")
        else:
            df_tran.columns = [c.strip() for c in df_tran.columns]
            
            # Hàm xử lý thời gian an toàn, loại bỏ 100% lỗi so sánh lệch múi giờ
            def ep_kieu_tg_safe(val):
                try:
                    dt_parsed = pd.to_datetime(val)
                    # QUAN TRỌNG: giá trị rỗng/không hợp lệ sẽ trả về NaT thay vì raise exception,
                    # nên phải kiểm tra riêng, nếu không NaT sẽ "lọt" qua try/except và làm crash
                    # ở bước .strftime() phía sau (NaTType does not support strftime).
                    if pd.isna(dt_parsed):
                        return thoi_gian_hien_tai
                    # QUAN TRỌNG (fix lệch giờ): Các trận nhập qua Google Sheet dạng text thuần
                    # (vd "2026-06-29 10:00:00") sẽ được parse thành giờ "naive" (không tz) -> giữ nguyên.
                    # Nhưng các trận được ghi qua Admin form thường được Apps Script lưu dưới dạng
                    # Date object, khi trả JSON sẽ tự serialize thành chuỗi ISO UTC (hậu tố "Z"),
                    # ví dụ giờ Việt Nam 10:00 sẽ trả về "...T03:00:00.000Z". Nếu chỉ cắt bỏ tzinfo mà
                    # không quy đổi, giờ sẽ bị lệch SỚM HƠN 7 tiếng so với giờ đã thiết lập trong Sheet.
                    # => Phải convert đúng sang giờ Việt Nam (UTC+7) trước khi bỏ tzinfo.
                    if dt_parsed.tzinfo is not None:
                        dt_parsed = dt_parsed.tz_convert('Asia/Ho_Chi_Minh')
                    return dt_parsed.to_pydatetime().replace(tzinfo=None)
                except:
                    return thoi_gian_hien_tai
            
            df_tran['dt_khoa_sort'] = df_tran['Thoi_Gian_Khoa_Form'].apply(ep_kieu_tg_safe)
            
            # ƯU TIÊN ĐƯA CÁC TRẬN SẮP KHÓA FORM (gần nhất) LÊN ĐẦU
            df_tran = df_tran.sort_values(by='dt_khoa_sort', ascending=True).reset_index(drop=True)
            
            # Tạo mặc định nếu cột Active chưa tồn tại trên Sheet
            if 'Active' not in df_tran.columns:
                df_tran['Active'] = 'Hiện'
            
            # Xác định danh sách mã trận mà nhân viên hiện tại ĐÃ bình chọn,
            # để tự động đưa trận đó vào section Ẩn (thu gọn) - đúng concept:
            # "bình chọn xong thì đưa vào section ẩn/hiện, mặc định là ẩn"
            danh_sach_ma_da_vote = set()
            df_cache_check = st.session_state["df_phieu_cache"]
            if co_du_cot(df_cache_check, ["Ma_NV", "Ma_Tran_Hoac_Doi_Voi", "Loai_Du_Doan"]):
                df_cache_check = df_cache_check.copy()
                # SO KHỚP BẰNG MÃ ĐÃ CHUẨN HÓA (xem sinh_cac_khoa_ma_tran): tránh mất dấu vết
                # phiếu vote cũ khi mã trận lệch hoa-thường/khoảng trắng/gạch ngang/số 0 đầu,
                # và ĐẶC BIỆT xử lý trường hợp Google Sheets tự đổi mã trận "04-04" thành
                # kiểu Ngày tháng (nguyên nhân chính khiến trận 4-xx bị "quên vote").
                df_cache_check["Ma_Tran_KhoaSet"] = df_cache_check["Ma_Tran_Hoac_Doi_Voi"].apply(sinh_cac_khoa_ma_tran)
                for khoa_set in df_cache_check[
                    (df_cache_check["Ma_NV"].apply(chuan_hoa_ma_nv) == chuan_hoa_ma_nv(ma_nv_selected)) &
                    (df_cache_check["Loai_Du_Doan"] == "Tran_Dau")
                ]["Ma_Tran_KhoaSet"]:
                    danh_sach_ma_da_vote |= khoa_set
            
            df_tran['Ma_Tran_Key'] = df_tran['Ma_Tran'].apply(chuan_hoa_ma_tran)
            df_tran['Da_Vote'] = df_tran['Ma_Tran_Key'].isin(danh_sach_ma_da_vote)


            # Trận đã quá hạn khóa cổng (dt_khoa_sort đã tính ở trên) -> phải tự động
            # thu gọn vào section Ẩn dù nhân viên CHƯA từng vote (trước đây code chỉ ẩn
            # khi Đã vote hoặc Admin ẩn, khiến trận đã đóng cổng mãi nằm ở section chính).
            df_tran['Da_Dong_Cong'] = df_tran['dt_khoa_sort'] < thoi_gian_hien_tai

            # Phân nhóm Trận đấu:
            # - Section HIỆN (mặc định mở): trận CHƯA bình chọn, CHƯA hết hạn khóa cổng, và Active != 'Ẩn'
            # - Section ẨN (mặc định thu gọn): trận ĐÃ bình chọn HOẶC ĐÃ đóng cổng HOẶC bị Admin đặt Active = 'Ẩn'
            df_dang_mo_hien = df_tran[
                (df_tran['Active'].astype(str).str.strip() != 'Ẩn') &
                (~df_tran['Da_Vote']) &
                (~df_tran['Da_Dong_Cong'])
            ]
            df_da_gom_an = df_tran[
                (df_tran['Active'].astype(str).str.strip() == 'Ẩn') |
                (df_tran['Da_Vote']) |
                (df_tran['Da_Dong_Cong'])
            ]

            # Hàm dựng giao diện từng dòng trận đấu
            def render_giao_dien_tran(row_data, idx_key):
                ma_tran = str(row_data.get("Ma_Tran", idx_key)).strip()
                doi_left = row_data.get("Doi_Left", "Đội A")
                doi_right = row_data.get("Doi_Right", "Đội B")
                han_mo = ep_kieu_tg_safe(row_data.get("Thoi_Gian_Mo_Form"))
                han_khoa = ep_kieu_tg_safe(row_data.get("Thoi_Gian_Khoa_Form"))
                
                st.markdown(f"#### ⚽ Trận {ma_tran}: {doi_left} vs {doi_right}")
                
                da_du_doan_tran = pd.DataFrame()
                if co_du_cot(st.session_state["df_phieu_cache"], ["Ma_NV", "Ma_Tran_Hoac_Doi_Voi", "Du_Doan"]):
                    st.session_state["df_phieu_cache"]["Ma_Tran_Hoac_Doi_Voi"] = st.session_state["df_phieu_cache"]["Ma_Tran_Hoac_Doi_Voi"].astype(str).str.strip()
                    # So khớp bằng bộ khóa suy rộng (xem sinh_cac_khoa_ma_tran) để không bỏ sót
                    # phiếu vote cũ nếu mã trận hiện tại lệch hoa/thường/khoảng trắng, HOẶC bị
                    # Google Sheets tự đổi thành kiểu Ngày tháng.
                    ma_tran_khoa_muc_tieu = chuan_hoa_ma_tran(ma_tran)
                    da_du_doan_tran = st.session_state["df_phieu_cache"][
                        (st.session_state["df_phieu_cache"]["Ma_NV"].apply(chuan_hoa_ma_nv) == chuan_hoa_ma_nv(ma_nv_selected)) & 
                        (st.session_state["df_phieu_cache"]["Ma_Tran_Hoac_Doi_Voi"].apply(
                            lambda x: ma_tran_khoa_muc_tieu in sinh_cac_khoa_ma_tran(x)
                        ))
                    ]
                
                # Trường hợp: Cổng bình chọn CHƯA MỞ (chưa tới Thoi_Gian_Mo_Form) - bug cũ: không hề kiểm tra mốc này
                if thoi_gian_hien_tai < han_mo:
                    st.warning(f"⏳ Cổng bình chọn trận này chưa mở. Sẽ mở lúc: **{han_mo.strftime('%H:%M %d/%m/%Y')}**.")
                # Trường hợp: Trận đấu đã quá hạn khóa cổng
                elif thoi_gian_hien_tai > han_khoa:
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
                                
                                # Đẩy dữ liệu lên Cloud TRƯỚC; chỉ cập nhật cache RAM khi Cloud
                                # xác nhận lưu thành công. Trước đây code cập nhật RAM ngay lập tức
                                # (optimistic) rồi mới gửi Cloud, khiến giao diện hiện "đã vote"
                                # NGAY CẢ KHI việc lưu lên Cloud thất bại -> qua lần F5 sau (tải lại
                                # dữ liệu thật từ Cloud) thì phiếu biến mất, gây hiểu lầm mất dữ liệu.
                                try:
                                    res_t = requests.post(URL_API_SCRIPT, data=payload_tran, timeout=8)
                                    luu_thanh_cong = kiem_tra_luu_thanh_cong(res_t.text)
                                    noi_dung_phan_hoi = res_t.text
                                except requests.exceptions.RequestException as e:
                                    luu_thanh_cong = False
                                    noi_dung_phan_hoi = str(e)

                                if luu_thanh_cong:
                                    df_c = st.session_state["df_phieu_cache"]
                                    mask_t = (df_c["Ma_NV"].apply(chuan_hoa_ma_nv) == chuan_hoa_ma_nv(ma_nv_selected)) & (df_c["Ma_Tran_Hoac_Doi_Voi"].apply(lambda x: chuan_hoa_ma_tran(ma_tran) in sinh_cac_khoa_ma_tran(x)))

                                    if mask_t.any():
                                        df_c.loc[mask_t, "Du_Doan"] = lua_chon
                                        df_c.loc[mask_t, "Timestamp"] = payload_tran["Timestamp"]
                                        df_c.loc[mask_t, "Phut_Nop_Som"] = phut_som_tran
                                    else:
                                        st.session_state["df_phieu_cache"] = pd.concat([df_c, pd.DataFrame([payload_tran])], ignore_index=True)

                                    st.session_state["thong_bao_loi_luu"] = None
                                    st.toast(f"⚽ Đã lưu Trận {ma_tran}: {lua_chon}")
                                else:
                                    # KHÔNG cập nhật cache RAM -> giao diện sẽ giữ đúng trạng thái
                                    # "chưa vote" (đúng với thực tế trên Cloud), tránh hiện sai.
                                    st.session_state["thong_bao_loi_luu"] = (
                                        f"❌ LƯU THẤT BẠI cho Trận {ma_tran} ({doi_left} [{lua_chon}] {doi_right}). "
                                        f"Lựa chọn của bạn CHƯA được ghi nhận lên hệ thống, vui lòng chọn lại và "
                                        f"bấm 'Xác nhận gửi!' một lần nữa. (Phản hồi từ Cloud: {noi_dung_phan_hoi})"
                                    )

                                st.rerun()
                st.markdown("---")

            # 1. Vẽ cụm các trận CHƯA bình chọn (và không bị Admin ẩn) lên màn hình chính, trận gần nhất lên đầu
            if not df_dang_mo_hien.empty:
                for index, row in df_dang_mo_hien.iterrows():
                    render_giao_dien_tran(row, f"hien_{index}")
            else:
                st.info("🎉 Bạn đã bình chọn hết các trận hiện có! Xem lại lựa chọn ở mục thu gọn bên dưới.")
                
            # 2. Vẽ cụm các trận ĐÃ bình chọn / bị Admin ẩn vào Expander thu gọn (mặc định đóng)
            if not df_da_gom_an.empty:
                with st.expander(f"📦 Xem các trận đã bình chọn / đã ẩn ({len(df_da_gom_an)} trận)", expanded=False):
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

    # --- HÀM TÍNH BẢNG XẾP HẠNG DÙNG CHUNG (có thể lọc theo danh sách mã trận của từng vòng) ---
    def tinh_bang_xep_hang(df_phieu_nguon, df_tran_nguon, danh_sach_ma_tran=None):
        """
        Tính bảng tổng soát điểm dự đoán trận đấu.
        - danh_sach_ma_tran = None -> tính TẤT CẢ các trận (bảng tổng chung cuộc).
        - danh_sach_ma_tran = [list mã trận] -> chỉ tính riêng các trận thuộc danh sách đó (theo từng vòng).
        Trả về:
            None           -> thiếu dữ liệu cột bắt buộc (Mã NV/Họ tên/Bộ phận)
            DataFrame rỗng -> không có dữ liệu phù hợp (chưa ai dự đoán / vòng đấu chưa có kết quả)
            DataFrame      -> bảng xếp hạng đã tính xong, đã sort và đánh số thứ tự
        """
        if not co_du_cot(df_tran_nguon, ["Ma_Tran", "Ket_Qua_Thuc_Te"]) or not co_du_cot(df_phieu_nguon, ["Loai_Du_Doan"]) or df_phieu_nguon[df_phieu_nguon['Loai_Du_Doan'] == 'Tran_Dau'].empty:
            return pd.DataFrame()

        # SO KHỚP BẰNG BỘ KHÓA SUY RỘNG: nếu không xử lý, một phiếu vote có mã trận
        # lệch hoa/thường/khoảng trắng, HOẶC bị Google Sheets tự đổi thành kiểu Ngày
        # tháng (vd "04-04" -> ngày 4/4) so với mã trận hiện tại sẽ bị .map() trả về
        # NaN -> không bao giờ được tính điểm ở BXH.
        dict_ket_qua = dict(zip(
            df_tran_nguon['Ma_Tran'].astype(str).apply(chuan_hoa_ma_tran),
            df_tran_nguon['Ket_Qua_Thuc_Te']
        ))

        def _quy_ve_khoa_hop_le(gia_tri_tho):
            for khoa in sinh_cac_khoa_ma_tran(gia_tri_tho):
                if khoa in dict_ket_qua:
                    return khoa
            return chuan_hoa_ma_tran(gia_tri_tho)

        df_du_doan_tran = df_phieu_nguon[df_phieu_nguon['Loai_Du_Doan'] == 'Tran_Dau'].copy()
        df_du_doan_tran['Ma_Tran_Hoac_Doi_Voi'] = df_du_doan_tran['Ma_Tran_Hoac_Doi_Voi'].astype(str).str.strip()
        df_du_doan_tran['Ma_Tran_Key'] = df_du_doan_tran['Ma_Tran_Hoac_Doi_Voi'].apply(_quy_ve_khoa_hop_le)

        # CHỈ TÍNH 1 LƯỢT SUBMIT DUY NHẤT CHO MỖI (NHÂN VIÊN, MÃ TRẬN):
        # Trước đây mỗi dòng phiếu bầu đều được cộng điểm riêng, nên nếu 1 người
        # lỡ bấm nộp nhiều lần cho CÙNG 1 trận (double-click, nộp lại...) thì điểm/phút
        # sớm bị NHÂN ĐÔI/BA một cách sai lệch. Quy tắc đúng:
        # - Nếu user chỉ nộp 1 lần -> tính lượt đó như bình thường.
        # - Nếu user nộp nhiều lần cho cùng 1 mã trận nhưng KHÔNG đổi dự đoán
        #   -> vẫn chỉ tính 1 lượt duy nhất (không cộng dồn).
        # - Nếu lượt nộp SAU thay đổi dự đoán so với lượt trước (user sửa lại lựa
        #   chọn) -> tính theo lượt SAU CÙNG (mới nhất), coi như bản cập nhật đúng.
        # => Cả 2 trường hợp trên đều được xử lý gọn bằng cách sắp theo Timestamp
        # rồi chỉ giữ lại DÒNG CUỐI CÙNG của mỗi (Ma_NV, Ma_Tran_Key).
        df_du_doan_tran['_ts_sap_xep'] = pd.to_datetime(df_du_doan_tran['Timestamp'], errors='coerce')
        df_du_doan_tran = df_du_doan_tran.sort_values(by='_ts_sap_xep', na_position='first', kind='stable')
        df_du_doan_tran = df_du_doan_tran.drop_duplicates(subset=['Ma_NV', 'Ma_Tran_Key'], keep='last')
        df_du_doan_tran = df_du_doan_tran.drop(columns=['_ts_sap_xep'])

        # Lọc riêng các trận thuộc vòng đấu được chỉ định (nếu có)
        if danh_sach_ma_tran is not None:
            danh_sach_ma_tran_key = [chuan_hoa_ma_tran(m) for m in danh_sach_ma_tran]
            df_du_doan_tran = df_du_doan_tran[df_du_doan_tran['Ma_Tran_Key'].isin(danh_sach_ma_tran_key)]

        if df_du_doan_tran.empty:
            return pd.DataFrame()

        df_du_doan_tran['Ket_Qua_Thuc_Te'] = df_du_doan_tran['Ma_Tran_Key'].map(dict_ket_qua)
        df_du_doan_tran['Diem'] = df_du_doan_tran.apply(lambda r: 3 if r['Du_Doan'] == r['Ket_Qua_Thuc_Te'] else 0, axis=1)
        df_du_doan_tran['Phut_Som_Hop_Le'] = df_du_doan_tran.apply(lambda r: an_toan_int(r.get('Phut_Nop_Som')) if r['Diem'] == 3 else 0, axis=1)

        if not co_du_cot(df_du_doan_tran, ["Ma_NV", "Ho_Ten", "Bo_Phan"]):
            return None

        bxh = df_du_doan_tran.groupby(['Ma_NV', 'Ho_Ten', 'Bo_Phan']).agg(
            Tong_Diem=('Diem', 'sum'),
            Tong_Phut_Som=('Phut_Som_Hop_Le', 'sum')
        ).reset_index()

        bxh = bxh.sort_values(by=['Tong_Diem', 'Tong_Phut_Som'], ascending=[False, False]).reset_index(drop=True)
        bxh.index += 1
        return bxh

    # --- HÀM HIỂN THỊ BẢNG XẾP HẠNG RA GIAO DIỆN ---
    def hien_thi_bang_xep_hang(bxh, thong_bao_khi_rong):
        if bxh is None:
            st.warning("⚠️ Dữ liệu phiếu bầu thiếu thông tin Mã NV/Họ tên/Bộ phận, không thể tổng hợp bảng xếp hạng.")
        elif bxh.empty:
            st.info(thong_bao_khi_rong)
        else:
            st.dataframe(bxh.rename(columns={
                'Ma_NV': 'Mã Nhân Viên', 'Ho_Ten': 'Họ và Tên', 'Bo_Phan': 'Bộ Phận',
                'Tong_Diem': 'Tổng Điểm', 'Tong_Phut_Som': 'Tổng Phút Sớm'
            }), use_container_width=True)

    # --- ĐỊNH NGHĨA DANH SÁCH MÃ TRẬN CHO TỪNG VÒNG ĐẤU ---
    ma_tran_vong_16 = [f"16-{i:02d}" for i in range(1, 17)]   # 16-01 -> 16-16 (Vòng 1/16)
    ma_tran_vong_8 = [f"16_{i:02d}" for i in range(1, 9)]     # 16_01 -> 16_08 (Vòng 1/8)
    ma_tran_vong_4 = [f"4-{i:02d}" for i in range(1, 5)]      # 4-01 -> 4-04 (Vòng 1/4 - Tứ kết)
    ma_tran_vong_2 = [f"02_{i:02d}" for i in range(1, 9)]     # 02_01 -> 02-02 (Vòng 1/2 - Bán kết)
    ma_tran_vong_1 = [f"01_{i:02d}" for i in range(1, 2)]     # 01_01 -> 01-02 (Vòng 1/1 - Bán kết)

    st.header("🏆 1. Bảng Tổng Điểm Dự Đoán Trận Đấu (Chung Cuộc)")
    bxh_chung_cuoc = tinh_bang_xep_hang(df_phieu, df_tran, danh_sach_ma_tran=None)
    hien_thi_bang_xep_hang(bxh_chung_cuoc, "Chưa có đủ dữ liệu trên Cloud để phân tích kết quả xếp hạng.")

    st.markdown("---")
    st.header("🥈 2. Bảng Tổng Soát Vòng 1/16")
    bxh_vong_16 = tinh_bang_xep_hang(df_phieu, df_tran, danh_sach_ma_tran=ma_tran_vong_16)
    hien_thi_bang_xep_hang(bxh_vong_16, "Chưa có dữ liệu dự đoán/kết quả cho Vòng 1/16.")

    st.markdown("---")
    st.header("🥉 3. Bảng Tổng Soát Vòng 1/8")
    bxh_vong_8 = tinh_bang_xep_hang(df_phieu, df_tran, danh_sach_ma_tran=ma_tran_vong_8)
    hien_thi_bang_xep_hang(bxh_vong_8, "Chưa có dữ liệu dự đoán/kết quả cho Vòng 1/8.")

    st.markdown("---")
    st.header("🎖️ 4. Bảng Tổng Soát Vòng 1/4 (Tứ Kết)")
    bxh_vong_4 = tinh_bang_xep_hang(df_phieu, df_tran, danh_sach_ma_tran=ma_tran_vong_4)
    hien_thi_bang_xep_hang(bxh_vong_4, "Chưa có dữ liệu dự đoán/kết quả cho Vòng Tứ Kết.")

    st.markdown("---")
    st.header("🎖️ 5. Bảng Tổng Soát Vòng 1/2 (Bán Kết)")
    bxh_vong_2 = tinh_bang_xep_hang(df_phieu, df_tran, danh_sach_ma_tran=ma_tran_vong_2)
    hien_thi_bang_xep_hang(bxh_vong_2, "Chưa có dữ liệu dự đoán/kết quả cho Vòng Tứ Kết.")

     st.markdown("---")
    st.header("🎖️ 6. Bảng Tổng Soát Vòng 1/1 (Chung Kết)")
    bxh_vong_1 = tinh_bang_xep_hang(df_phieu, df_tran, danh_sach_ma_tran=ma_tran_vong_1)
    hien_thi_bang_xep_hang(bxh_vong_1, "Chưa có dữ liệu dự đoán/kết quả cho Vòng Tứ Kết.")

    st.markdown("---")
    st.header("🔮 7. Danh Sách Lựa Chọn Đội Vô Địch World Cup 2026")
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
        
        tab1, tab2, tab3 = st.tabs(["➕ Thêm Trận Đấu Mới", "✏️ Cập Nhật Kết Quả Trận Đấu", "🔍 Kiểm Tra Lệch Mã Trận"])
        
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

        with tab3:
            st.header("Kiểm tra Mã trận đấu bị lệch (mất phiếu vote / mất điểm)")
            st.caption(
                "Công cụ này so sánh mã trận trong các phiếu bầu đã lưu với danh sách "
                "trận đấu hiện đang có trên hệ thống. Nếu một mã trận trong phiếu bầu "
                "KHÔNG khớp với bất kỳ trận nào hiện tại (do gõ lại mã trận lệch hoa/thường, "
                "khoảng trắng, ký tự gạch ngang, HOẶC do Google Sheets tự động đổi mã trận "
                "dạng số như \"04-04\" thành kiểu Ngày tháng vì cột chưa được định dạng "
                "Văn bản thuần), phiếu đó sẽ bị 'mồ côi': nhân viên sẽ thấy như chưa từng "
                "vote và điểm số không được tính ở Bảng xếp hạng."
            )
            df_tran_ck = tai_tran_dau_cloud()
            df_phieu_ck = tai_phieu_bau_cloud()

            if not co_du_cot(df_tran_ck, ["Ma_Tran"]) or not co_du_cot(df_phieu_ck, ["Ma_Tran_Hoac_Doi_Voi", "Loai_Du_Doan"]):
                st.info("Chưa đủ dữ liệu (trận đấu hoặc phiếu bầu) để kiểm tra.")
            else:
                ma_tran_hien_tai_key = set(df_tran_ck["Ma_Tran"].astype(str).apply(chuan_hoa_ma_tran))
                df_vote_tran = df_phieu_ck[df_phieu_ck["Loai_Du_Doan"] == "Tran_Dau"].copy()
                df_vote_tran["Ma_Tran_KhoaSet"] = df_vote_tran["Ma_Tran_Hoac_Doi_Voi"].astype(str).apply(sinh_cac_khoa_ma_tran)
                df_mo_coi = df_vote_tran[df_vote_tran["Ma_Tran_KhoaSet"].apply(lambda s: s.isdisjoint(ma_tran_hien_tai_key))]

                if df_mo_coi.empty:
                    st.success("✅ Không phát hiện phiếu vote nào bị lệch mã trận. Toàn bộ phiếu đều khớp với trận đấu hiện tại.")
                else:
                    st.warning(f"⚠️ Phát hiện {len(df_mo_coi)} phiếu vote có mã trận KHÔNG khớp với trận nào hiện tại:")
                    cac_cot_hien = [c for c in ["Ma_NV", "Ho_Ten", "Ma_Tran_Hoac_Doi_Voi", "Du_Doan", "Timestamp"] if c in df_mo_coi.columns]
                    st.dataframe(df_mo_coi[cac_cot_hien].reset_index(drop=True), use_container_width=True)
                    st.caption(
                        "➡️ Cách sửa: vào Google Sheet 'phieu_bau', sửa lại giá trị cột Ma_Tran_Hoac_Doi_Voi "
                        "của các dòng trên cho khớp CHÍNH XÁC với mã trận đang hiển thị ở tab 'Cập Nhật Kết Quả "
                        "Trận Đấu' (ví dụ đổi '4-01' viết hoa/thường hoặc gạch ngang cho đúng)."
                    )
    elif mat_khau != "":
        st.error("Sai mã bảo mật Quản trị!")
