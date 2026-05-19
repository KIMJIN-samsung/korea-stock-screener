"""
한국 주식 종목 스크리너
조건: 투자경고 종목 ∩ 외국인 N일 연속 순매수 ∩ 프로그램 N일 연속 순매수
"""

import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from pykrx import stock

# ============================
# 페이지 설정
# ============================
st.set_page_config(
    page_title="종목 스크리너",
    page_icon="📊",
    layout="wide",
)


# ============================
# 데이터 조회 함수
# ============================

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_warning_stocks_auto(trd_dd: str) -> pd.DataFrame:
    """KRX에서 투자경고 종목 자동 조회 (실패할 수 있음 - 미국 IP 차단 가능성)"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd",
        }
        url = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
        payload = {
            "bld": "dbms/MDC/STAT/standard/MDCSTAT09501",  # 시장경보 종목 지정현황
            "mktId": "ALL",
            "trdDd": trd_dd,
            "money": "1",
        }
        r = requests.post(url, data=payload, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()

        block = data.get("OutBlock_1", []) or data.get("output", [])
        if not block:
            return pd.DataFrame()

        df = pd.DataFrame(block)
        # 컬럼명이 환경에 따라 다를 수 있어 후보를 두루 시도
        ticker_col = next((c for c in ["ISU_SRT_CD", "ISU_CD", "종목코드"] if c in df.columns), None)
        name_col = next((c for c in ["ISU_ABBRV", "ISU_NM", "종목명"] if c in df.columns), None)
        type_col = next((c for c in ["DSGN_TP_NM", "지정구분"] if c in df.columns), None)

        if not ticker_col or not type_col:
            return pd.DataFrame()

        # 투자경고만 필터
        df = df[df[type_col].astype(str).str.contains("투자경고", na=False)].copy()
        df["종목코드"] = df[ticker_col].astype(str).str.zfill(6)
        df["종목명"] = df[name_col] if name_col else ""
        return df[["종목코드", "종목명"]].drop_duplicates().reset_index(drop=True)
    except Exception as e:
        st.warning(f"자동 조회 실패: {e}. 수동 입력 모드를 사용해주세요.")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_investor_net_buying(ticker: str, days_back: int = 20) -> pd.DataFrame:
    """종목의 일자별 투자자 순매수(거래대금 기준)"""
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days_back + 15)).strftime("%Y%m%d")
    try:
        df = stock.get_market_trading_value_by_date(
            start_date, end_date, ticker, detail=True
        )
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_program_net_buying(ticker: str, days_back: int = 20) -> pd.DataFrame:
    """종목의 일자별 프로그램 매매 데이터"""
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days_back + 15)).strftime("%Y%m%d")
    try:
        df = stock.get_program_trading_by_date(start_date, end_date, ticker)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_current_price(ticker: str) -> tuple:
    """현재가와 등락률 조회"""
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=5)).strftime("%Y%m%d")
    try:
        df = stock.get_market_ohlcv(start_date, end_date, ticker)
        if df.empty:
            return 0, 0.0
        price = int(df["종가"].iloc[-1])
        change = float(df["등락률"].iloc[-1])
        return price, change
    except Exception:
        return 0, 0.0


def count_consecutive_positive(values) -> int:
    """리스트의 마지막부터 연속된 양수의 개수를 셈"""
    if values is None or len(values) == 0:
        return 0
    count = 0
    for v in reversed(list(values)):
        try:
            if float(v) > 0:
                count += 1
            else:
                break
        except (TypeError, ValueError):
            break
    return count


def pick_column(df: pd.DataFrame, candidates: list) -> str:
    """DataFrame에서 후보 컬럼명 중 첫 번째로 존재하는 것 반환"""
    for c in candidates:
        if c in df.columns:
            return c
    # 부분 매칭 시도
    for c in candidates:
        for col in df.columns:
            if c in col:
                return col
    return None


# ============================
# 메인 UI
# ============================

st.title("📊 한국 주식 종목 스크리너")
st.caption("투자경고 종목 ∩ 외국인 연속 순매수 ∩ 프로그램 연속 순매수")

# 사이드바
with st.sidebar:
    st.header("⚙️ 조건 설정")
    foreign_days = st.slider("외국인 연속 순매수 (일)", 3, 10, 5)
    program_days = st.slider("프로그램 연속 순매수 (일)", 3, 10, 5)

    st.divider()
    st.header("📋 투자경고 종목 소스")
    source_mode = st.radio(
        "조회 방식",
        ["자동 (KRX 스크래핑)", "수동 입력"],
        help="자동이 실패하면 수동 입력을 사용하세요.",
    )

    manual_text = ""
    if source_mode == "수동 입력":
        st.markdown(
            "[KRX 시장경보종목 페이지 열기](http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020303)"
        )
        manual_text = st.text_area(
            "종목코드 (쉼표 또는 줄바꿈 구분)",
            placeholder="예: 005930, 000660\n또는 줄바꿈으로 구분",
            height=120,
        )

# 메인 영역
top_l, top_r = st.columns([3, 1])
with top_l:
    st.markdown(f"**오늘 날짜:** {datetime.now().strftime('%Y-%m-%d')}")
with top_r:
    run = st.button("🔍 조회", type="primary", use_container_width=True)

if run:
    today = datetime.now().strftime("%Y%m%d")

    # 1) 투자경고 종목 확보
    if source_mode == "자동 (KRX 스크래핑)":
        with st.spinner("투자경고 종목 조회 중..."):
            warning_df = fetch_warning_stocks_auto(today)
        if warning_df.empty:
            st.error("자동 조회 실패. 사이드바에서 '수동 입력'으로 전환해주세요.")
            st.stop()
        tickers = warning_df["종목코드"].tolist()
        names = dict(zip(warning_df["종목코드"], warning_df["종목명"]))
    else:
        raw = manual_text.replace("\n", ",").replace(" ", "")
        tickers = [t.zfill(6) for t in raw.split(",") if t.strip().isdigit()]
        if not tickers:
            st.error("종목코드를 1개 이상 입력해주세요.")
            st.stop()
        names = {}
        for t in tickers:
            try:
                names[t] = stock.get_market_ticker_name(t)
            except Exception:
                names[t] = ""

    st.success(f"투자경고 종목 {len(tickers)}개 분석 시작")

    # 2) 종목별 분석
    results = []
    progress = st.progress(0.0)
    status = st.empty()

    for idx, ticker in enumerate(tickers):
        status.text(f"분석 중 ({idx + 1}/{len(tickers)}): {names.get(ticker, ticker)}")

        # 외국인 연속 순매수
        inv_df = get_investor_net_buying(ticker)
        foreign_consec = 0
        if not inv_df.empty:
            col = pick_column(inv_df, ["외국인합계", "외국인"])
            if col:
                foreign_consec = count_consecutive_positive(inv_df[col].values)

        # 프로그램 연속 순매수
        prog_df = get_program_net_buying(ticker)
        program_consec = 0
        if not prog_df.empty:
            col = pick_column(prog_df, ["전체_순매수", "순매수", "전체"])
            if col:
                program_consec = count_consecutive_positive(prog_df[col].values)

        # 현재가
        price, change = get_current_price(ticker)

        passes = (foreign_consec >= foreign_days) and (program_consec >= program_days)
        results.append({
            "종목코드": ticker,
            "종목명": names.get(ticker, ""),
            "현재가": price,
            "등락률(%)": change,
            "외국인 연속일": foreign_consec,
            "프로그램 연속일": program_consec,
            "통과": "✅" if passes else "❌",
        })

        progress.progress((idx + 1) / len(tickers))
        time.sleep(0.1)  # KRX 부하 방지

    progress.empty()
    status.empty()

    # 3) 결과 표시
    result_df = pd.DataFrame(results)

    st.divider()
    st.subheader("🎯 조건 통과 종목")
    passed = result_df[result_df["통과"] == "✅"].copy()
    if not passed.empty:
        passed = passed.sort_values("외국인 연속일", ascending=False)
        st.dataframe(passed, use_container_width=True, hide_index=True)
        st.success(f"{len(passed)}개 종목이 모든 조건을 통과했습니다.")
    else:
        st.info("조건을 통과한 종목이 없습니다. 슬라이더 값을 낮춰서 다시 시도해보세요.")

    with st.expander("📂 전체 분석 결과 보기"):
        full = result_df.sort_values(
            ["외국인 연속일", "프로그램 연속일"], ascending=False
        )
        st.dataframe(full, use_container_width=True, hide_index=True)

else:
    st.info("👈 사이드바에서 조건을 설정한 뒤 **[조회]** 버튼을 눌러주세요.")
    with st.expander("ℹ️ 사용 안내"):
        st.markdown(
            """
            ### 동작 방식
            1. 사이드바에서 외국인·프로그램 연속 순매수일을 슬라이더로 설정
            2. **투자경고 종목** 리스트를 자동(KRX) 또는 수동으로 확보
            3. 각 종목의 최근 영업일까지 외국인·프로그램 순매수 연속일수 계산
            4. 두 조건을 모두 만족하는 종목 표시

            ### 주의 사항
            - 데이터는 KRX 정보데이터시스템 기반이며 **1시간 캐싱**됩니다
            - **Streamlit Cloud(미국 서버)에서 자동 조회가 차단될 수 있습니다**
              → 그 경우 사이드바의 **수동 입력** 모드를 이용하세요
            - 자동 조회 실패 시: KRX 페이지에서 종목코드를 복사해 붙여넣기
            """
        )
