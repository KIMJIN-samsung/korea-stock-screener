# 한국 주식 종목 스크리너

투자경고 종목 중에서 **외국인 N일 연속 순매수** + **프로그램 N일 연속 순매수** 조건을 동시에 만족하는 종목을 찾아주는 Streamlit 웹앱.

## 기능
- 슬라이더로 연속 매수일수 조정 (3~10일)
- 투자경고 종목 자동 조회 (KRX) + 수동 입력 폴백
- 결과 테이블: 종목명, 현재가, 등락률, 연속 매수일수
- 1시간 데이터 캐싱

---

## 배포 가이드 (비개발자용)

### 1단계 — GitHub 계정 만들기
1. https://github.com/signup 접속
2. 이메일·비밀번호·아이디 입력해서 계정 생성 (무료)
3. 이메일 인증까지 완료

### 2단계 — 새 저장소(repository) 만들기
1. 우측 상단 `+` 버튼 → **New repository** 클릭
2. Repository name: `korea-stock-screener` (아무 이름이나 OK)
3. **Public** 선택 (Streamlit Cloud 무료 플랜에 필요)
4. **Add a README file** 체크
5. **Create repository** 클릭

### 3단계 — 파일 3개 업로드
저장소 페이지에서 **Add file → Upload files** 클릭 후 아래 3개 파일을 드래그 앤 드롭:
- `app.py`
- `requirements.txt`
- `README.md` (이 파일, 선택사항)

업로드 후 페이지 하단의 **Commit changes** 클릭.

### 4단계 — Streamlit Cloud 배포
1. https://share.streamlit.io 접속
2. **Continue with GitHub** 으로 로그인
3. **Create app** 클릭
4. 다음을 선택:
   - Repository: 방금 만든 `korea-stock-screener`
   - Branch: `main`
   - Main file path: `app.py`
5. **Deploy!** 클릭
6. 1~3분 기다리면 앱 URL이 생성됨 (`https://xxx.streamlit.app`)

### 5단계 — 휴대폰에 추가
생성된 URL을 휴대폰 브라우저에서 열고:
- iOS: 공유 → **홈 화면에 추가**
- Android: 메뉴(⋮) → **홈 화면에 추가**

홈 화면 아이콘처럼 사용 가능.

---

## 사용 방법
1. 사이드바에서 외국인·프로그램 연속 순매수일 설정 (기본 5일)
2. **조회 방식** 선택
   - `자동`: KRX에서 투자경고 종목 자동 가져옴 (실패 가능)
   - `수동 입력`: KRX 페이지에서 직접 종목코드 복사·붙여넣기
3. **조회** 버튼 클릭 → 결과 확인

---

## 알아둘 사항

### 자동 조회 실패 시
Streamlit Cloud는 미국 서버라 KRX가 봇 차단할 수 있습니다.  
실패 시 사이드바의 **수동 입력** 모드 사용:
1. https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020303 접속
2. 시장경보 종류에서 **투자경고** 필터링
3. 종목코드 복사 → 앱 텍스트박스에 붙여넣기

### 코드 수정이 필요해질 때
- KRX 사이트 변경 등으로 앱이 깨지면 Claude에게 다시 와서 도움 요청
- GitHub에서 `app.py` 우측 상단 연필 아이콘(✏️)으로 직접 편집 가능
- 수정 후 **Commit changes** 누르면 1~2분 내 Streamlit Cloud 자동 재배포

### 조건 추가하고 싶을 때
처음에 정한 외국인·프로그램 연속 순매수 외에 새 조건이 필요하면 Claude에게 요청 → 수정된 `app.py` 받음 → GitHub에서 파일 교체.
