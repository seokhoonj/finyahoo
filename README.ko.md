# finyahoo

[![check](https://github.com/seokhoonj/finyahoo/actions/workflows/check.yml/badge.svg)](https://github.com/seokhoonj/finyahoo/actions/workflows/check.yml)
[![PyPI](https://img.shields.io/pypi/v/finyahoo)](https://pypi.org/project/finyahoo/)
[![Python](https://img.shields.io/pypi/pyversions/finyahoo)](https://pypi.org/project/finyahoo/)
[![License](https://img.shields.io/pypi/l/finyahoo)](https://github.com/seokhoonj/finyahoo/blob/main/LICENSE)

[English](README.md) | **한국어**

Yahoo Finance의 시세와 기업정보를 읽어옵니다.

일·주·월봉의 시가·고가·저가·종가·거래량과 수정종가, 배당·액면분할 내역, 기업
펀더멘털(섹터·시가총액·밸류에이션 등), 실시간 시세, 옵션, 종목 스크리너, 뉴스까지 다룹니다.

## 1. 설치

```sh
pip install finyahoo
```

Python 3.11 이상이 필요합니다.

## 2. 빠른 시작

```python
from finyahoo import YahooClient

yahoo = YahooClient()
history = yahoo.fetch_history("AAPL", start="2020-01-01")
latest = history.bars[-1]
print(latest.trade_date, latest.close, latest.adj_close, latest.volume)
print(len(history.splits), "splits,", len(history.dividends), "dividends")

profile = yahoo.fetch_profile("AAPL")
print(profile.sector, profile.market_cap, profile.trailing_pe)
```

심볼은 Yahoo 티커입니다: 미국주는 그대로(`AAPL`), 한국주는 시장 접미사(`005930.KS`
코스피, `.KQ` 코스닥), 지수는 캐럿 접두(`^GSPC`)를 씁니다. 폐지·미상 티커는 빈 결과가
아니라 `YahooRequestError`를 냅니다.

## 3. 클라이언트 옵션

`YahooClient`는 두 개의 선택 설정을 받습니다(둘 다 키워드 전용):

| 인자 | 기본값 | 하는 일 |
|---|---|---|
| `timeout` | `30.0` | 요청당 제한 시간(초) |
| `delay_seconds` | `0.5` | 연속 요청 사이의 간격; 여러 심볼을 잇달아 읽다가 요청 제한에 걸리면 늘리세요 |

```python
yahoo = YahooClient(timeout=10, delay_seconds=1.0)
```

## 4. 메서드

| 메서드 | 반환 |
|---|---|
| `fetch_history(symbol, *, start, end, timeframe)` | `PriceHistory` — OHLCV 봉 + `Split`/`Dividend` 이벤트 |
| `fetch_profile(symbol)` | `Profile` — 한 종목의 현재 펀더멘털 스냅샷 |
| `fetch_quotes(symbols)` | `tuple[Quote]` — 종목별 실시간 시세 스냅샷 |
| `fetch_search(query, *, quotes_count, news_count)` | `Search` — 종목 매칭 + 관련 뉴스 |
| `fetch_timeseries(symbol, metric_types, *, start, end)` | `tuple[FinancialSeries]` — 날짜 있는 재무 항목 |
| `fetch_spark(symbols, *, period, interval)` | `tuple[Spark]` — 종목별 간이 종가 시계열 |
| `fetch_options(symbol, *, expiration)` | `OptionChain` — 한 만기의 콜/풋 |
| `fetch_recommendations(symbol)` | `tuple[Recommendation]` — 유사 종목 |
| `fetch_insights(symbol)` | `Insights` — 목표가·밸류에이션·전망·리포트 |
| `fetch_screener(screen_id, *, page_size)` | `Screen` — 사전정의 스크린 구성종목(`Quote`) |

### 핵심 두 가지

- `fetch_history` — `PriceHistory`: OHLCV 봉(`close`는 수정주가, `adj_close`는 배당까지
  반영)과, 같은 구간에 있었던 `Split`·`Dividend` 이벤트를 데이터로 함께 담습니다. 양
  끝 경계는 포함(inclusive)이며, 둘 다 기본값은 Yahoo가 가진 가장 넓은 구간입니다.
- `fetch_profile` — `Profile`: 한 종목의 펀더멘털(섹터·규모·밸류에이션·성장·마진)에
  관한 지금 시점의 스냅샷을 담습니다. 이력이 아니며, 모든 수치 필드는 선택적이라
  없는 값은 `0`이 아니라 `None`입니다.

## 5. 데이터프레임

결과를 pandas·polars로 바로 표(DataFrame)로 만들 수 있습니다:

```python
import pandas as pd
prices = pd.DataFrame(history.bars).set_index("trade_date")
```

```python
import polars as pl
prices = pl.DataFrame(history.bars)
```

`history.splits`·`history.dividends`, 스크린의 `members`, `fetch_quotes(...)` 결과도 같은 방식입니다.

## 6. 터미널

패키지를 설치하면 `finyahoo` 명령이 PATH에 등록됩니다 (`python -m finyahoo`로도 실행).

```sh
finyahoo history AAPL --start 2024-01-01  # OHLCV 봉 + 분할/배당 이벤트
finyahoo history ^GSPC --timeframe week   # 지수의 주봉
finyahoo profile AAPL                     # 현재 펀더멘털
finyahoo profile 005930.KS --json         # 전체 스냅샷을 JSON으로
finyahoo quote MU                         # 한 종목 실시간 시세
```

각 서브커맨드 모두 기본은 읽기 좋은 요약, `--json`은 전체 결과를 냅니다. 어느 것이든
`--help`(`finyahoo quote --help`)로 옵션을 확인하세요. `quote`는 심볼 하나를 받아 실시간
시세 스냅샷을 보여주고, `profile`은 해당 종목의 펀더멘털을 보여줍니다.

### 예시 출력

`finyahoo history 005930.KS`는 한 줄 요약과 최근 봉을 다음과 같이 보여줍니다.

```
005930.KS  6643 bars  (2 splits, 59 dividends)
  2026-07-24  close 249,500.0000  adj 249,500.0000  vol 26,175,580
  2026-07-27  close 254,000.0000  adj 254,000.0000  vol 23,296,044
  2026-07-28  close 220,000.0000  adj 220,000.0000  vol 41,639,623
  2026-07-29  close 208,500.0000  adj 208,500.0000  vol 65,555,523
  2026-07-30  close 207,000.0000  adj 207,000.0000  vol 50,259,720
```

`finyahoo profile 005930.KS`는 기업 펀더멘털을 다음과 같이 보여줍니다.

```
symbol               005930.KS
name                 Samsung Electronics Co., Ltd.
sector               Technology
industry             Consumer Electronics
currency             KRW
market_cap           1359278631813120
shares_outstanding   5764191903
forward_pe           3.1737533
revenue_growth       0.692
earnings_growth      4.921
profit_margin        0.21459
operating_margin     0.42751
return_on_equity     0.18855
fifty_two_week_high  374500.0
fifty_two_week_low   67500.0
beta                 1.479
```

`finyahoo quote 005930.KS`는 장 마감 후의 실시간 시세 스냅샷을 보여주며, 국내 거래소 종목이므로 프리마켓·애프터마켓 필드는 없습니다.

```
symbol                   005930.KS
name                     Samsung Electronics Co., Ltd.
quote_type               EQUITY
exchange                 KSE
currency                 KRW
market_state             POSTPOST
price                    207000.0
previous_close           208500.0
change                   -1500.0
change_percent           -0.7194245
day_open                 214000.0
day_high                 226000.0
day_low                  202000.0
volume                   50259720
market_time              2026-07-30 06:30:23+00:00
fifty_day_average        301250.0
two_hundred_day_average  193301.25
```

표시된 값은 조회 시점 기준의 스냅샷입니다.

## 7. AI 코딩 에이전트에서 사용

이 저장소는 Claude Code·Codex용 플러그인 마켓플레이스도 겸합니다 —
`history`·`profile`·`quote`를 `finyahoo` 명령을 호출하는 스킬로 제공합니다. 먼저 위에서
패키지를 설치하세요(키·로그인 불필요).

### 7.1. Claude Code

```
/plugin marketplace add seokhoonj/finyahoo
/plugin install finyahoo@finyahoo
```

그런 다음 평범하게 물어보거나("AAPL 프로파일 보여줘", "MU 지금 얼마야?"), 스킬을 직접
호출하세요 — `/finyahoo:history ^GSPC`, `/finyahoo:profile AAPL`, `/finyahoo:quote MU`.

### 7.2. Codex

```
codex plugin marketplace add seokhoonj/finyahoo
codex plugin add finyahoo@finyahoo
```

`history`·`profile`·`quote` 스킬은 심볼에 반응하며, `finyahoo quote <symbol>`로 직접
실행해도 됩니다.

플러그인 없이 쓰려면? 스킬을 스킬 디렉터리에 symlink해 bare 형식(`/history`)으로 부르세요:

```sh
ln -s "$PWD/plugins/finyahoo/skills/history" ~/.claude/skills/history
```

## 8. 라이선스

MIT
