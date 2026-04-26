# Stock Swing Agents

한국 주식 스윙 매매를 위한 Agent voting 보조 엔진입니다. 자동매매가 아니라, 실시간/준실시간으로 확인한 데이터와 공시/테마 정보를 같은 형식으로 넣고 `진입 가능 / 대기 / 관망 / 금지` 판단을 내리도록 설계했습니다.

## 구성

- `Market Data Agent`: 가격, 거래량, 거래대금, 지수, 환율 흐름
- `Technical Signal Agent`: 추세, 이동평균, RSI, MACD, 지지/저항
- `Supply/Demand Agent`: 외국인, 기관, 개인, 프로그램 수급
- `News/Disclosure Agent`: 뉴스, 경제 이벤트, DART 공시 위험
- `Theme/Sector Agent`: 주도 테마, 대장주 여부, 테마 반복성
- `Theme Following Agent`: 테마 파일 기반 최근성, 반복성, 상승/하락성, 추종 후보군
- `Yang-Eum-Yang Agent`: 양봉-음봉-양봉 눌림 패턴, 음봉 거래량 60% 이하, 5일선/10일선 지지 여부
- `Risk Guard Agent`: 손절, 변동성, 거래정지/투자주의/악성 공시 리스크
- `Execution Timing Agent`: 지금 진입, 눌림 대기, 분할 진입 조건
- `Post-Trade Review Agent`: 최근 매매 원칙 준수와 복기 기록

`Risk Guard Agent`가 `block`을 내면 최종 판단은 항상 `금지`입니다.

## 사용법

샘플 데이터로 실행:

```powershell
python -m stock_swing_agents.cli --stock "세림B&G"
```

JSON 입력으로 실행:

```powershell
python -m stock_swing_agents.cli --input examples/sample_snapshot.json
```

테마 파일을 같이 반영:

```powershell
python -m stock_swing_agents.cli --input examples/sample_snapshot.json --theme-file "C:\Users\guswl\OneDrive\문서\gpt\theme_week_2026_W18_2th.txt"
```

특정 테마를 우선 추종:

```powershell
python -m stock_swing_agents.cli --stock "세림B&G" --theme "탈 플라스틱" --theme-file "C:\Users\guswl\OneDrive\문서\gpt\theme_week_2026_W18_2th.txt"
```

JSON 결과 출력:

```powershell
python -m stock_swing_agents.cli --input examples/sample_snapshot.json --json
```

## 입력 원칙

가격/수급/이벤트 데이터는 실행 직전에 확인한 값을 넣습니다. 각 데이터에는 가능한 한 `sources`를 포함해 출처, 조회시각, 지연 여부를 보존합니다.

`yang_eum_yang` 입력은 PDF의 양음양 조건을 구조화한 값입니다.

- `pattern`: `pattern1`, `pattern2`, `pattern3`
- `first_candle_gain_pct`: 첫 장대양봉 상승률. 기본 유효 구간은 5~20%
- `pullback_volume_pct_of_first`: 음봉/눌림 거래량이 첫 양봉 거래량 대비 몇 %인지. Pattern 1은 60% 이하를 우호적으로 봅니다.
- `pullback_holds_ma5`, `current_above_short_ma`, `short_ma_distance_pct`: 5일선/10일선 등 단기 이평선 지지와 거리
- `pullback_low_broken`, `short_ma_broken`, `opening_volume_spike`: 발생 시 감점되는 위험 조건

권장 출처:

- 실시간/이벤트: Investing.com Economic Calendar
- 한국 시장 시세/수급: KRX 정보데이터시스템
- 공시/재무: OpenDART

## 테스트

```powershell
python -m unittest discover -s tests
```
