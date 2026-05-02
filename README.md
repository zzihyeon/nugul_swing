# Multi-Agent Stock Picker

한국 주식 스윙/단타 후보를 RS 우선순위로 정렬하고 9개 Agent가 독립 평가한 뒤, Health veto와 Voting을 반영해 한국어 리포트와 JSON을 함께 생성하는 시스템입니다.

초기 버전은 외부 API 없이 mock provider로 end-to-end 실행됩니다. 실제 가격, 뉴스, 공시, 수급 API는 `src/data_providers`의 Provider 인터페이스를 교체해 붙이면 됩니다.

## 실행

```powershell
cd stock_picker_agents
python -m src.main --universe kospi_kosdaq --top-n 10 --realtime
```

특정 종목만 실행:

```powershell
python -m src.main --tickers 000660,005930,010120 --top-n 5 --refresh
```

JSON 파일 저장:

```powershell
python -m src.main --universe kosdaq150 --market-cap-min 300000000000 --rs-top-n 100 --output-json data/cache/latest_result.json
```

SQLite cache warm-up with external Naver provider:

```powershell
python -m src.main --provider naver --universe kospi_kosdaq --universe-limit 100 --top-n 20 --realtime --cache-db data/cache/stock_picker.sqlite3 --warm-cache --output-json data/cache/latest_result.json
```

Run from SQLite cache only, without API calls:

```powershell
python -m src.main --provider naver --universe kospi_kosdaq --universe-limit 100 --top-n 20 --cache-db data/cache/stock_picker.sqlite3 --cache-only
```

Use cache first when it is fresh, and call API only when missing or stale:

```powershell
python -m src.main --provider naver --universe kospi_kosdaq --universe-limit 100 --top-n 20 --cache-db data/cache/stock_picker.sqlite3 --cache-ttl-minutes 15
```

Use SQLite as the base store, compare each ticker's last cached OHLCV date with the latest market index date, and refresh only missing ticker contexts:

```powershell
python -m src.main --provider naver --universe kospi_kosdaq --universe-limit 700 --top-n 20 --cache-db data/cache/stock_picker.sqlite3 --incremental-cache
```

Keep a collector running to refresh SQLite periodically:

```powershell
python -m src.main --provider naver --universe kospi_kosdaq --universe-limit 100 --cache-db data/cache/stock_picker.sqlite3 --collector-loop --collector-interval-minutes 15
```

리포트만 생략하고 JSON 중심 출력:

```powershell
python -m src.main --tickers 000660,010120 --include-report false
```

## 파이프라인

1. Universe 생성 및 시가총액 3,000억 원 필터
2. 가격, 거래량, 거래대금, 시총, 뉴스, 수급, 공시 최신화
3. RS Agent가 시장 대비 상대강도로 1차 정렬
4. RS 상위 후보를 9개 Agent가 독립 평가
5. Voting Engine이 RS bucket 우선 정렬, Health veto, confidence 보정을 적용
6. 한국어 Markdown 리포트와 machine-readable JSON 출력

## Agent

- `RS Agent`: 시장/섹터 대비 상대강도와 RS 순위
- `Theme Agent`: 테마 강도, 확산 단계, 대장주 여부
- `Health Agent`: 재무, 유동성, 공시, 관리/거래정지/투자경고 veto
- `Trader Agent`: 분할매수, 분할매도, 손절, 무효화 조건
- `Breakout Agent`: 박스권/전고점/신고가 돌파 가능성
- `Pullback Agent`: 5/10/20일선 눌림, 거래량 감소, 양음양 후보
- `Scalping Agent`: 당일 거래대금, VWAP, 변동성, 뉴스 반응
- `Volume Flow Agent`: 거래량 증가율, 거래대금, 외국인/기관/프로그램 수급
- `Custom Document Agent`: `data/custom_docs/yyang_eum_yyang.pdf` 기반 양음양 규칙 평가

## 설정

핵심 기준은 모두 `config/*.yaml`에서 수정합니다.

- `market_cap_filter.yaml`: 시가총액 기준과 unknown 처리
- `rs_config.yaml`: RS window, benchmark, RS top N
- `agent_weights.yaml`: Agent별 voting weight
- `risk_rules.yaml`: veto 및 위험 감점 규칙
- `yyang_eum_yyang_rules.yaml`: 양음양 pattern rule
- `realtime_config.yaml`: 장중/장마감 stale 기준

## 테스트

```powershell
cd stock_picker_agents
python -m unittest discover -s tests
```

테스트는 시총 필터, RS 우선 정렬, RS bucket 내 Voting 정렬, Health veto, stale 판단, 양음양 Pattern 1/2/3, 문서 규칙 추출, 전체 mock 실행을 검증합니다.

## 주의

이 프로젝트는 매매 의사결정을 보조하는 분석 엔진입니다. 자동매매 주문 기능은 포함하지 않으며, 실거래 전에는 실제 데이터 Provider와 체결/호가/공시 검증을 별도로 붙여야 합니다.
