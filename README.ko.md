# pyyahoo

[![check](https://github.com/seokhoonj/pyyahoo/actions/workflows/check.yml/badge.svg)](https://github.com/seokhoonj/pyyahoo/actions/workflows/check.yml)
[![PyPI](https://img.shields.io/pypi/v/pyyahoo)](https://pypi.org/project/pyyahoo/)
[![Python](https://img.shields.io/pypi/pyversions/pyyahoo)](https://pypi.org/project/pyyahoo/)
[![License](https://img.shields.io/pypi/l/pyyahoo)](https://github.com/seokhoonj/pyyahoo/blob/main/LICENSE)

[English](README.md) | **한국어**

Yahoo Finance에서 시세와 기업정보를 하나의 타입드 클라이언트로 읽는다.

Yahoo는 **공식 API가 없다.** pyyahoo는 finance.yahoo.com 웹앱이 내부적으로 쓰는
문서 없는(undocumented) JSON 엔드포인트를 그대로 호출하고, 응답을 타입드
결과로 모델링한다. 이 엔드포인트들은 예고 없이 바뀔 수 있어서, 응답 모양이
달라지면 파서가 조용히 비는 대신 명확히 실패한다.

```python
from datetime import date
from pyyahoo import YahooClient

with YahooClient() as yahoo:
    history = yahoo.fetch_history("AAPL", start=date(2020, 1, 1))
    print(history.bars[-1])        # PriceBar(trade_date=..., close=..., adj_close=..., volume=...)
    print(history.splits)          # (Split(ex_date=..., numerator=..., denominator=...), ...)

    profile = yahoo.fetch_profile("AAPL")
    print(profile.sector, profile.market_cap, profile.trailing_pe)
```

## 하나의 클라이언트가 닿는 곳

| 메서드 | 엔드포인트 | crumb | 반환 |
|---|---|:--:|---|
| `fetch_history(symbol, *, start, end, timeframe)` | chart | | `PriceHistory` — OHLCV 봉 + `Split`/`Dividend` 이벤트 |
| `fetch_profile(symbol)` | quoteSummary | ✓ | `Profile` — 현재 펀더멘털 스냅샷 |
| `fetch_quotes(symbols)` | quote | ✓ | `tuple[Quote]` — 종목별 실시간 스냅샷 |
| `fetch_search(query, *, quotes_count, news_count)` | search | | `Search` — 종목 매칭 + 관련 뉴스 |
| `fetch_timeseries(symbol, metric_types, *, start, end)` | timeseries | | `tuple[FinancialSeries]` — 날짜 있는 재무 항목 |
| `fetch_spark(symbols, *, period, interval)` | spark | | `tuple[Spark]` — 종목별 간이 종가 시계열 |
| `fetch_options(symbol, *, expiration)` | options | ✓ | `OptionChain` — 한 만기의 콜/풋 |
| `fetch_recommendations(symbol)` | recommendationsbysymbol | | `tuple[Recommendation]` — 유사 종목 |
| `fetch_insights(symbol)` | insights | ✓ | `Insights` — 목표가·밸류에이션·전망·리포트 |
| `fetch_screener(screen_id, *, page_size)` | screener/predefined | ✓ | `Screen` — 사전정의 스크린 구성종목(`Quote`) |

crumb(Yahoo가 일부 엔드포인트에서 요구하는 세션 토큰)는 자동으로 발급·재발급된다.

### 핵심 두 가지

- `fetch_history` — `PriceHistory`: OHLCV 봉(`close`는 수정주가, `adj_close`는 배당까지
  반영), 그리고 같은 구간에 있었던 `Split`·`Dividend` 이벤트를 데이터로 함께
  담는다. 양 끝 경계는 포함(inclusive)이고, 둘 다 기본값은 Yahoo가 가진 가장 넓은
  구간이다.
- `fetch_profile` — `Profile`: 기업의 현재 펀더멘털(섹터·규모·밸류에이션·성장·마진).
  이력이 아니라 지금 시점 스냅샷이며, 모든 수치 필드는 옵셔널이라 없는 값은 `0`이
  아니라 `None`이다.

심볼은 Yahoo 티커다: 미국주는 그대로(`MU`), 한국주는 시장 접미사(`005930.KS` 코스피,
`.KQ` 코스닥), 지수는 캐럿 접두(`^GSPC`). 폐지·미상 티커는 빈 결과가 아니라
`YahooRequestError`를 낸다.

## 설치

```sh
pip install pyyahoo
```

Python 3.11 이상 필요.

## 라이선스

MIT
