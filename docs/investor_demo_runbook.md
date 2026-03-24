# Investor Demo Runbook

## 목적
EliOra의 선수/팀 인사이트 프로토타입을 투자자에게 **짧고 명확하게** 설명하는 5분 데모 플로우.

---

## 시작 전 체크리스트 (1분)
- 로컬 실행: `python -m http.server 8000 -d docs`
- 열기:
  - Executive: `http://localhost:8000/site/executive-demo.html`
  - ST: `http://localhost:8000/site/player-st.html`
  - Team: `http://localhost:8000/site/team-prototype.html`
- 브라우저 줌 100%, 탭은 미리 열어 두기

---

## 5분 데모 플로우

### 1) Executive Demo (30–45초)
- 핵심 메시지: **“결정 지능(Decision Intelligence)으로 스카우팅/전술/퍼포먼스 의사결정 속도와 정확도를 높인다.”**
- 두 개의 실물 프로토타입이 지금 바로 동작함을 강조.

### 2) ST Prototype (2분)
- **Radar / Benchmark**: 빠르게 선수 프로필 차이 확인
- **Bubble**: 선택한 스타일 지표로 전체 풀 탐색
- **Role & Fit Intelligence**: 
  - 역할 추천 + 신뢰도
  - 유사 스타일 컴프
  - 팀 핏 리스트

### 3) Team Prototype (2분)
- **Process vs Results / Style Map**: 팀 스타일과 결과를 한눈에
- **Points Drivers**: 왜 성과가 나는지 설명 가능
- **Table**: 필터 기반 탐색 가능

### 4) 마무리 (15초)
- “이미 작동하는 프로토타입 + 확장 가능한 모델링 로드맵” 강조

---

## 백업 플로우 (차트가 복잡해 보일 때)
- ST: Preset 버튼(예: False 9, Target Man) → Radar + Role & Fit만 보여주기
- Team: Points Drivers 탭 → Process 상위 5 지표 강조

---

## 예상 질문 & 답변

**Q: 이게 실제 영입 의사결정에 어떻게 쓰이나요?**  
A: 유사 스타일/핏/프로세스 기반으로 shortlist를 빠르게 만들고, 스카우트 리소스를 효율화합니다.

**Q: 모델의 신뢰성은?**  
A: 지표는 시즌 단위로 교차검증했고, 프로세스 기반 모델을 강조합니다. 결과-접근 변수는 분리해서 투명하게 보여줍니다.

**Q: 왜 레이더가 필요한가요?**  
A: 여러 핵심 지표를 짧게 비교할 때 가장 직관적인 요약 도구입니다. 더 빠른 시각적 스냅샷을 제공합니다.

**Q: 로컬이 아니라도 사용할 수 있나요?**  
A: 네, GitHub Pages로 정적 배포 가능하며 백엔드 없이 작동합니다.

---

## 이미 구현된 것 vs 다음 단계

### 이미 구현됨
- 선수/팀 비교, 유사도, 역할/핏 인텔리전스, 모델 기반 Points Drivers
- 필터/내보내기/요약 리포트

### 다음 단계
- 포지션별 세부 모델
- 클럽 KPI 가중치 커스터마이징
- 스카우팅 워크플로우 자동화

---

## 발표 톤 가이드
- “**데이터는 결정을 돕는 도구**”라는 톤 유지
- “**설명 가능하고 투명한 모델**” 강조
- 과도한 인과 주장 금지 (association/driver 중심)
