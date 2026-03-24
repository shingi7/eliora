# Presentation Assets — Capture Workflow

## 목표
다음 4개의 스크린샷을 확보해 투자자 데크 또는 메일 첨부용으로 사용합니다.

- ST 페이지 히어로 화면
- Team 페이지 히어로 화면
- Points Drivers 섹션
- Executive Demo 랜딩 페이지

---

## 권장 캡처 방법 (수동)
1. 로컬 서버 실행
   ```bash
   python -m http.server 8000 -d docs
   ```
2. 브라우저 100% 줌, 전체 화면
3. 아래 URL 순서대로 오픈 후 캡처
   - `http://localhost:8000/site/executive-demo.html`
   - `http://localhost:8000/site/player-st.html#tab-overview`
   - `http://localhost:8000/site/team-prototype.html#tab-overview`
   - `http://localhost:8000/site/team-prototype.html#tab-drivers`
4. 파일명 예시
   - `exec_demo_hero.png`
   - `st_hero.png`
   - `team_hero.png`
   - `team_points_drivers.png`

---

## 선택사항: 자동 캡처 (macOS)
아래는 수동 캡처를 빠르게 돕는 선택 옵션입니다.

1) Safari 또는 Chrome에서 페이지를 연 뒤
2) macOS 기본 단축키 사용
- 전체 화면: `Shift + Command + 3`
- 선택 영역: `Shift + Command + 4`

---

## 품질 체크
- 텍스트가 잘리지 않도록 스크롤 위치 확인
- 탭이 활성화된 상태인지 확인
- 레이더/버블/포인트 드라이버 차트가 렌더 완료된 뒤 캡처
