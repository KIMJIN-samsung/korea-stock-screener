"""
한국 주식 종목 스크리너 (단순화 버전)
조건: 외국인 N일 연속 순매수 ∩ 프로그램 N일 연속 순매수
"""

import streamlit as st
import pandas as pd
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
# 데이터 함수
# ============================

@st.cache_data(ttl=3600, show_spinner=False)
def get_recent_trading_days(n_days: int) -> list:
    """최근 N개 거래일 (오래된 순서)"""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=n_days * 2 + 14)).strftime("%Y%m%d")
    try:
        df = stock.get_index_ohlcv(start, end, "1001")  # KOSPI 지수
        dates = df.index.strftime("%Y%m%d").tolist()
        return dates[-n_days:]
    except Exception as e:
        st.error(f"거래일 조회 실패: {e}")
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def get_foreign_net_value_on_day(date: str, market: str) -> pd.Series:
    """특정일 모든 종목의 외국인 순매수거래대금"""
    try:
        df = stock.get_market_net_purchases_of_equities(date, date, market, "외국인")
        col = next(
            (c for c in df.columns if "순매수거래대금" in c),
            next((c for c in df.columns if "순매수" in c and "대금" in c), None),
        )
        if col is None:
            col = df.select_dtypes(include="number").columns[-1]
        return df[col]
    except Exception as e:
        st.warning(f"{date} 외국인 데이터 실패: {e}")
        return pd.Series(dtype=float)


@st.cache_data(ttl=3600, show_spinner=False)
def get_program_net_value_on_day(date: str, market: str) -> pd.Series:
    """특정일 모든 종목의 프로그램 전체_순매수"""
    try:
        if market == "ALL":
            kospi = stock.get_program_trading_by_ticker(date, "KOSPI")
            kosdaq = stock.get_program_trading_by_ticker(date, "KOSDAQ")
            df = pd.concat([kospi, kosdaq])
        else:
            df = stock.get_program_trading_by_ticker(date, market)

        col = next(
            (c for c in df.columns if "전체_순매수" in c),
            next((c for c in df.columns if "순매수" in c), None),
        )
        if col is None:
            col = df.select_dtypes(include="number").columns[-1]
        return df[col]
    except Exception as e:
        st.warning(f"{date} 프로그램 데이터 실패: {e}")
        return pd.Series(dtype=float)


def build_matrix(dates: list, market: str, fetcher) -> pd.DataFrame:
    """각 일자별 Series를 종목×일자 매트릭스로 결합"""
    parts = []
    for d in dates:
        s = fetcher(d, market)
        s.name = d
        parts.append(s)
        time.sleep(0.3)  # KRX 부하 방지
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, axis=1)


def count_consecutive_positive_from_end(row) -> int:
    """행의 마지막부터 연속된 양수 개수"""
    count = 0
    for v in reversed(row.tolist()):
        if pd.notna(v) and v > 0:
            count += 1
        else:
            break
    return count


@st.cache_data(ttl=3600, show_spinner=False)
def get_market_snapshot(date: str, market: str) -> pd.DataFrame:
    """오늘자 모든 종목의 종가/등락률 (한 번에 조회)"""
    try:
        if market == "ALL":
            kospi = stock.get_market_ohlcv_by_ticker(date, "KOSPI")
            kosdaq = stock.get_market_ohlcv_by_ticker(date, "KOSDAQ")
            return pd.concat([kospi, kosdaq])
        return stock.get_market_ohlcv_by_ticker(date, market)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=86400, show_spinner=False)
def get_ticker_name_map(date: str, market: str) -> dict:
    """종목코드 → 종목명 매핑"""
    try:
        if market == "ALL":
            kospi = stock.get_market_ticker_list(date, market="KOSPI")
            kosdaq = stock.get_market_ticker_list(date, market="KOSDAQ")
            tickers = kospi + kosdaq
        else:
            tickers = stock.get_market_ticker_list(date, market=market)
        return {t: stock.get_market_ticker_name(t) for t in tickers}
    except Exception:
        return {}


# ============================
# UI
# ============================

st.title("📊 한국 주식 종목 스크리너")
st.caption("외국인 N일 연속 순매수 ∩ 프로그램 N일 연속 순매수")

with st.sidebar:
    st.header("⚙️ 조건 설정")
    foreign_days = st.slider("외국인 연속 순매수 (일)", 3, 10, 5)
    program_days = st.slider("프로그램 연속 순매수 (일)", 3, 10, 5)

    st.divider()
    st.header("📍 스캔 범위")
    market = st.selectbox(
        "시장",
        ["ALL", "KOSPI", "KOSDAQ"],
        index=0,
        help="ALL = KOSPI + KOSDAQ",
    )

# 메인
top_l, top_r = st.columns([3, 1])
with top_l:
    st.markdown(f"**오늘 날짜:** {datetime.now().strftime('%Y-%m-%d')}")
with top_r:
    run = st.button("🔍 조회", type="primary", use_container_width=True)

if run:
    max_days = max(foreign_days, program_days)

    # 1) 거래일 확보
    with st.spinner(f"최근 {max_days} 거래일 확인..."):
        days = get_recent_trading_days(max_days)
    if not days:
        st.error("거래일 조회 실패 — 잠시 후 다시 시도해주세요.")
        st.stop()
    st.info(f"분석 대상 거래일: **{days[0]} ~ {days[-1]}** ({len(days)}일)")

    # 2) 외국인 매트릭스
    with st.spinner("외국인 매매 데이터 수집 중... (일자당 1회 조회)"):
        foreign_mat = build_matrix(days, market, get_foreign_net_value_on_day)
    if foreign_mat.empty:
        st.error("외국인 데이터를 가져오지 못했습니다.")
        st.stop()

    # 3) 프로그램 매트릭스
    with st.spinner("프로그램 매매 데이터 수집 중..."):
        program_mat = build_matrix(days, market, get_program_net_value_on_day)
    if program_mat.empty:
        st.error("프로그램 데이터를 가져오지 못했습니다.")
        st.stop()

    # 4) 종목별 연속 양수 계산
    with st.spinner("연속 순매수일수 계산..."):
        foreign_consec = foreign_mat.apply(count_consecutive_positive_from_end, axis=1)
        program_consec = program_mat.apply(count_consecutive_positive_from_end, axis=1)

    # 5) 조건 통과 종목 추출
    common_tickers = foreign_consec.index.intersection(program_consec.index)
    foreign_pass = foreign_consec.loc[common_tickers] >= foreign_days
    program_pass = program_consec.loc[common_tickers] >= program_days
    passing = common_tickers[foreign_pass & program_pass]

    st.divider()

    if len(passing) == 0:
        st.info(
            f"조건을 통과한 종목이 없습니다. "
            f"슬라이더 값(외국인 {foreign_days}일, 프로그램 {program_days}일)을 낮춰서 다시 시도해보세요."
        )
        st.stop()

    # 6) 결과 테이블 구성 (일괄 조회로 성능 확보)
    today = days[-1]
    with st.spinner("종목 정보 수집 중..."):
        snapshot = get_market_snapshot(today, market)
        names = get_ticker_name_map(today, market)

    rows = []
    for t in passing:
        name = names.get(t, "")
        price, change = 0, 0.0
        if t in snapshot.index:
            try:
                price = int(snapshot.loc[t, "종가"])
                change = float(snapshot.loc[t, "등락률"])
            except Exception:
                pass
        rows.append({
            "종목코드": t,
            "종목명": name,
            "현재가": price,
            "등락률(%)": round(change, 2),
            "외국인 연속일": int(foreign_consec.loc[t]),
            "프로그램 연속일": int(program_consec.loc[t]),
        })

    result_df = pd.DataFrame(rows).sort_values(
        ["외국인 연속일", "프로그램 연속일"], ascending=False
    ).reset_index(drop=True)

    st.subheader(f"🎯 조건 통과 종목 ({len(result_df)}개)")
    st.dataframe(result_df, use_container_width=True, hide_index=True)

else:
    st.info("👈 사이드바에서 조건 설정 후 **[조회]** 버튼을 눌러주세요.")
    with st.expander("ℹ️ 동작 방식"):
        st.markdown(
            """
            ### 무엇을 하나요
            1. 사이드바의 슬라이더로 **연속 순매수 일수**(외국인·프로그램)와 **시장 범위** 설정
            2. 최근 N 거래일의 모든 종목 데이터를 일자별로 가져와 매트릭스 구성
            3. 두 조건을 동시에 만족하는 종목 추출
            4. 종목명, 현재가, 등락률, 연속일수 함께 표시

            ### 주의 사항
            - 데이터는 KRX 정보데이터시스템 기반 (`pykrx` 사용)
            - 1시간 캐싱 — 같은 조건으로 다시 조회하면 즉시 결과 표시
            - 최초 조회 시 시장 전체 데이터 수집으로 1~2분 소요될 수 있음
            """
        )
