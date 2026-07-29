# pyyahoo

[![check](https://github.com/seokhoonj/pyyahoo/actions/workflows/check.yml/badge.svg)](https://github.com/seokhoonj/pyyahoo/actions/workflows/check.yml)
[![PyPI](https://img.shields.io/pypi/v/pyyahoo)](https://pypi.org/project/pyyahoo/)
[![Python](https://img.shields.io/pypi/pyversions/pyyahoo)](https://pypi.org/project/pyyahoo/)
[![License](https://img.shields.io/pypi/l/pyyahoo)](https://github.com/seokhoonj/pyyahoo/blob/main/LICENSE)

[English](README.md) | **한국어**

Yahoo Finance의 시세와 기업정보를 타입이 지정된 하나의 클라이언트로 읽습니다.

OHLCV 시세 이력, 실시간 시세, 기업 펀더멘털, 옵션, 스크리너를 한 클라이언트로
가져오고, 결과는 전부 타입이 지정된 객체로 돌려받습니다.

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

## 메서드

| 메서드 | 반환 |
|---|---|
| `fetch_history(symbol, *, start, end, timeframe)` | `PriceHistory` — OHLCV 봉 + `Split`/`Dividend` 이벤트 |
| `fetch_profile(symbol)` | `Profile` — 현재 펀더멘털 스냅샷 |
| `fetch_quotes(symbols)` | `tuple[Quote]` — 종목별 실시간 스냅샷 |
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
- `fetch_profile` — `Profile`: 기업의 현재 펀더멘털(섹터·규모·밸류에이션·성장·마진)
  입니다. 이력이 아니라 지금 시점의 스냅샷이며, 모든 수치 필드는 선택적이라 없는 값은
  `0`이 아니라 `None`입니다.

심볼은 Yahoo 티커입니다: 미국주는 그대로(`AAPL`), 한국주는 시장 접미사(`005930.KS`
코스피, `.KQ` 코스닥), 지수는 캐럿 접두(`^GSPC`)를 씁니다. 폐지·미상 티커는 빈 결과가
아니라 `YahooRequestError`를 냅니다.

## 설치

```sh
pip install pyyahoo
```

Python 3.11 이상이 필요합니다.

## 명령줄

패키지를 설치하면 `pyyahoo` 명령이 PATH에 등록됩니다 (`python -m pyyahoo`로도 실행).

```sh
pyyahoo history AAPL --start 2024-01-01     # OHLCV 봉 + 분할/배당 이벤트
pyyahoo history ^GSPC --timeframe week      # 지수의 주봉
pyyahoo profile AAPL                         # 현재 펀더멘털
pyyahoo profile 005930.KS --json             # 전체 스냅샷을 JSON으로
```

두 서브커맨드 모두 기본은 읽기 좋은 요약, `--json`은 전체 결과를 냅니다.
`pyyahoo history --help` / `pyyahoo profile --help`로 옵션을 확인하세요.

## AI 코딩 에이전트에서 쓰기

이 저장소는 Claude Code·Codex용 플러그인 마켓플레이스도 겸합니다 — `history`·`profile`을
`pyyahoo` 명령을 호출하는 스킬로 제공합니다. 먼저 위에서 패키지를 설치하세요(키·로그인
불필요).

### Claude Code

```
/plugin marketplace add seokhoonj/pyyahoo
/plugin install pyyahoo@pyyahoo
```

그런 다음 평범하게 물어보거나("AAPL 프로파일 보여줘"), 스킬을 직접 호출하세요 —
`/pyyahoo:history ^GSPC`, `/pyyahoo:profile AAPL`.

### Codex

```
codex plugin marketplace add seokhoonj/pyyahoo
codex plugin add pyyahoo@pyyahoo
```

`history`·`profile` 스킬은 심볼에 반응하며, `pyyahoo history <symbol>`로 직접 실행해도
됩니다.

플러그인 없이 쓰려면? 스킬을 스킬 디렉터리에 symlink해 bare 형식(`/history`)으로 부르세요:

```sh
ln -s "$PWD/plugins/pyyahoo/skills/history" ~/.claude/skills/history
```

## 라이선스

MIT
