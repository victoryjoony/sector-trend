"""미국 섹터·테마 트렌드 대시보드 생성기.

세 층으로 본다.
  가격: 테마 ETF가 S&P 500보다 얼마나 더/덜 올랐나 (1·3·6개월 상대수익률)
  거래: 최근 20일 거래대금이 120일 평균보다 많은가
  관심: 관련 위키백과 문서 조회수가 최근 7일에 평소(그 전 8주)보다 늘었나
결과는 docs/index.html(휴대폰용 페이지)과 data/history.json(날짜별 점수 기록)에 쓴다.
"""
import html
import json
import time
import urllib.parse
import urllib.request
import warnings
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from themes import BENCH, THEMES

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent
KST = timezone(timedelta(hours=9))
UA = "sector-trend-dashboard/1.0 (https://github.com/victoryjoony/sector-trend)"
WEEK = 5  # 거래일 기준 1주

WEIGHTS = {"rs2w": 0.20, "rs1m": 0.35, "rs3m": 0.20, "vol": 0.15, "attn": 0.10}
ATTN_HOT, VOL_HOT = 1.15, 1.15


# ---------- 데이터 수집 ----------

def fetch_prices(tickers, period="2y"):
    df = yf.download(tickers, period=period, auto_adjust=True, progress=False, threads=True)
    # 장중에 돌면 오늘 행은 미완성 가격이라 버린다 (16:15 ET 이후에만 오늘 종가로 인정)
    now_et = pd.Timestamp.now(tz="America/New_York")
    if df.index[-1].date() == now_et.date() and (now_et.hour, now_et.minute) < (16, 15):
        df = df.iloc[:-1]
    return df["Close"].ffill(), df["Volume"].fillna(0)


def fetch_wiki(article, days=130):
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    start = end - timedelta(days=days)
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/"
           f"all-access/user/{urllib.parse.quote(article, safe='')}/daily/"
           f"{start:%Y%m%d}/{end:%Y%m%d}")
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                items = json.load(r)["items"]
            return pd.Series({pd.Timestamp(i["timestamp"][:8]): i["views"] for i in items}, dtype=float)
        except Exception as e:  # 429면 잠깐 쉬고 다시
            print(f"  wiki {article} 실패({e}), 재시도 {attempt + 1}")
            time.sleep(3 * (attempt + 1))
    return pd.Series(dtype=float)


def fetch_news(query, n=3):
    q = urllib.parse.quote(f"{query} when:3d")
    url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            root = ET.fromstring(r.read())
    except Exception as e:
        print(f"  news {query} 실패({e})")
        return []
    out = []
    for item in root.iter("item"):
        title = item.findtext("title", "")
        src = item.findtext("source", "")
        if src and title.endswith(" - " + src):
            title = title[: -len(src) - 3]
        out.append({"title": title, "link": item.findtext("link", ""), "source": src})
        if len(out) >= n:
            break
    return out


def fetch_holdings(etf, n=5):
    try:
        h = yf.Ticker(etf).funds_data.top_holdings.head(n)
        return [(t, str(name)) for t, name in zip(h.index, h["Name"])]
    except Exception as e:
        print(f"  holdings {etf} 실패({e})")
        return []


# ---------- 계산 ----------

def ret(s, n, at=-1):
    s = s.dropna()
    if len(s) < n + 1 - at:
        return np.nan
    return s.iloc[at] / s.iloc[at - n] - 1


def attention_ratio(views, asof):
    """asof 이전 7일 평균 / 그 전 56일 평균."""
    v = views[views.index <= asof]
    if len(v) < 63:
        return np.nan
    recent, base = v.iloc[-7:].mean(), v.iloc[-63:-7].mean()
    return recent / base if base > 0 else np.nan


def metrics(close, volume, wiki, at):
    """at = 거래일 위치(-1 오늘, -1-WEEK 1주 전)."""
    spy = close[BENCH[0]]
    asof = close.index[at]
    rows = []
    for tid, name, etf, arts, _ in THEMES:
        c = close[etf]
        dv = (close[etf] * volume[etf]).iloc[: len(close) + at + 1]
        vol = dv.iloc[-20:].mean() / dv.iloc[-120:].mean() if dv.iloc[-120:].mean() > 0 else np.nan
        found = [wiki[a] for a in arts if not wiki[a].empty]
        views = pd.concat(found, axis=1).sum(axis=1) if found else pd.Series(dtype=float)
        hist = c.dropna().iloc[: len(c.dropna()) + at + 1]
        rows.append({
            "id": tid, "name": name, "etf": etf,
            "rs2w": ret(c, 10, at) - ret(spy, 10, at),
            "rs1m": ret(c, 21, at) - ret(spy, 21, at),
            "rs3m": ret(c, 63, at) - ret(spy, 63, at),
            "rs6m": ret(c, 126, at) - ret(spy, 126, at),
            "r1w": ret(c, WEEK, at), "r1m": ret(c, 21, at),
            "vol": vol,
            "attn": attention_ratio(views, asof) if not views.empty else np.nan,
            "off_high": hist.iloc[-1] / hist.iloc[-252:].max() - 1,
        })
    df = pd.DataFrame(rows).set_index("id")
    pct = sum(df[k].rank(pct=True).fillna(0.5) * w for k, w in WEIGHTS.items())
    df["score"] = (pct * 100).round(0)
    df["rank"] = df["score"].rank(ascending=False, method="first").astype(int)
    return df.sort_values("rank")


def stage(r):
    """3개월(그동안)과 2주(지금)의 방향으로 나눈다."""
    if r.rs3m > 0:
        return ("주도", "lead") if r.rs2w >= 0 else ("식는 중", "cool")
    return ("떠오름", "rise") if r.rs2w > 0 else ("소외", "lag")


def early_signals(df):
    """가격보다 먼저 움직이는 경향이 있는 두 가지. 예측이 아니라 '지금 막 변하는 중'인 것."""
    turn = df[(df.rs3m <= 0) & (df.rs2w > 0)].sort_values("rs2w", ascending=False).head(5)
    buzz = df[((df.attn >= ATTN_HOT) | (df.vol >= VOL_HOT)) & (df.rs1m <= 0)]
    buzz = buzz.assign(k=buzz.attn.fillna(1) + buzz.vol.fillna(1)).sort_values("k", ascending=False).head(5)
    return turn, buzz


# ---------- 렌더링 ----------

def pct(x, digits=1, sign=True):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return f"{x * 100:+.{digits}f}%" if sign else f"{x * 100:.{digits}f}%"


def tone(x):
    if x is None or np.isnan(x):
        return ""
    return "up" if x > 0 else "down"


def sparkline(series, w=110, h=30):
    s = series.dropna().iloc[-126:]
    if len(s) < 10:
        return ""
    lo, hi = s.min(), s.max()
    span = hi - lo or 1
    pts = " ".join(f"{i / (len(s) - 1) * w:.1f},{h - (v - lo) / span * (h - 4) - 2:.1f}"
                   for i, v in enumerate(s))
    cls = "up" if s.iloc[-1] >= s.iloc[0] else "down"
    return (f'<svg class="spark {cls}" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'aria-hidden="true"><polyline points="{pts}"/></svg>')


def dots(r):
    marks = [("관심", r.attn >= ATTN_HOT if not np.isnan(r.attn) else False),
             ("거래", r.vol >= VOL_HOT if not np.isnan(r.vol) else False),
             ("가격", r.rs2w > 0 and r.rs1m > 0)]
    return "".join(f'<span class="dot{" on" if on else ""}">{lbl}</span>' for lbl, on in marks)


def rank_move(r, prev):
    if r.name not in prev.index:
        return ""
    d = int(prev.loc[r.name, "rank"] - r["rank"])
    if d > 0:
        return f'<span class="mv up">▲{d}</span>'
    if d < 0:
        return f'<span class="mv down">▼{-d}</span>'
    return '<span class="mv">–</span>'


def render(today, prev, close, holdings, news, asof, built):
    spy = close[BENCH[0]]
    e = html.escape

    # 요약 문장 (계산 결과만, 해석·권유 없음)
    top3 = today.head(3)
    moved = (prev["rank"] - today["rank"]).reindex(today.index).dropna().sort_values(ascending=False)
    riser = moved.index[0] if len(moved) and moved.iloc[0] > 0 else None
    faller = moved.index[-1] if len(moved) and moved.iloc[-1] < 0 else None
    all3 = [r for _, r in today.iterrows()
            if (r.attn >= ATTN_HOT) and (r.vol >= VOL_HOT) and r.rs2w > 0 and r.rs1m > 0]

    def early_list(rows, empty):
        if rows.empty:
            return f'<p class="sub">{empty}</p>'
        lis = "".join(
            f'<li><span class="nm">{e(r["name"])} <small>{e(r.etf)}</small></span>'
            f'<span class="meta">3개월 <b class="{tone(r.rs3m)}">{pct(r.rs3m)}</b> → 2주 <b class="{tone(r.rs2w)}">{pct(r.rs2w)}</b>'
            f' · 관심 {("–" if np.isnan(r.attn) else f"{r.attn:.2f}배")} · 거래 {r.vol:.2f}배</span></li>'
            for _, r in rows.iterrows())
        return f'<ul class="early">{lis}</ul>'

    turn, buzz = early_signals(today)

    summary = [f"점수 상위: " + ", ".join(f"<b>{e(r['name'])}</b>({stage(r)[0]})" for _, r in top3.iterrows())]
    if all3:
        summary.append("관심·거래·가격 세 층이 모두 켜진 테마: " + ", ".join(f"<b>{e(r['name'])}</b>" for r in all3))
    else:
        summary.append("관심·거래·가격 세 층이 모두 켜진 테마는 오늘 없음")
    if riser is not None:
        summary.append(f"1주간 순위 상승 1위: <b>{e(today.loc[riser, 'name'])}</b> "
                       f"({int(prev.loc[riser, 'rank'])}위 → {int(today.loc[riser, 'rank'])}위)")
    if faller is not None:
        summary.append(f"1주간 순위 하락 1위: <b>{e(today.loc[faller, 'name'])}</b> "
                       f"({int(prev.loc[faller, 'rank'])}위 → {int(today.loc[faller, 'rank'])}위)")

    # 테마 카드
    cards = []
    for tid, r in today.iterrows():
        st, cls = stage(r)
        rel = close[r.etf] / spy
        cards.append(f"""
<article class="card">
  <div class="row1">
    <span class="rk">{r['rank']}</span>
    <span class="nm">{e(r['name'])} <small>{e(r.etf)}</small></span>
    {rank_move(r, prev)}
    <span class="stage {cls}">{st}</span>
  </div>
  <div class="row2">
    <div class="nums">
      <div><label>2주</label><b class="{tone(r.rs2w)}">{pct(r.rs2w)}</b></div>
      <div><label>1개월</label><b class="{tone(r.rs1m)}">{pct(r.rs1m)}</b></div>
      <div><label>3개월</label><b class="{tone(r.rs3m)}">{pct(r.rs3m)}</b></div>
    </div>
    {sparkline(rel)}
  </div>
  <div class="row3">
    {dots(r)}
    <span class="meta">거래 {r.vol:.2f}배 · 관심 {('–' if np.isnan(r.attn) else f'{r.attn:.2f}배')} · 고점 대비 {pct(r.off_high, sign=False) if r.off_high < -0.0005 else '신고가'} · 점수 {int(r.score)}</span>
  </div>
</article>""")

    # 상위 테마의 대표 종목
    hold_html = []
    for tid in today.index[:8]:
        items = holdings.get(tid, [])
        if not items:
            continue
        lis = "".join(
            f'<li><span class="tk">{e(t)}</span><span class="hn">{e(n)}</span>'
            f'<b class="{tone(r1)}">{pct(r1)}</b><b class="{tone(r3)}">{pct(r3)}</b></li>'
            for t, n, r1, r3 in items)
        hold_html.append(f'<details><summary>{e(today.loc[tid, "name"])} <small>{e(today.loc[tid, "etf"])} 상위 보유</small></summary>'
                         f'<ul class="hold"><li class="hd"><span></span><span></span><b>1개월</b><b>3개월</b></li>{lis}</ul></details>')

    news_html = []
    for tid, items in news.items():
        if not items:
            continue
        lis = "".join(f'<li><a href="{e(i["link"])}" target="_blank" rel="noopener">{e(i["title"])}</a>'
                      f'<small>{e(i["source"])}</small></li>' for i in items)
        news_html.append(f'<h3>{e(today.loc[tid, "name"])}</h3><ul class="news">{lis}</ul>')

    spy1m, spy3m = ret(spy, 21), ret(spy, 63)
    qqq1m = ret(close["QQQ"], 21)

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="#0f1115">
<title>미국 섹터 트렌드</title>
<style>
:root {{
  --bg:#0f1115; --panel:#171a21; --line:#262b35; --text:#e6e8ec; --muted:#8b93a3;
  --up:#3ecf8e; --down:#f2667a; --accent:#7aa2ff;
  --lead:#3ecf8e; --rise:#7aa2ff; --cool:#f0b44c; --lag:#59606e;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text);
  font:15px/1.5 -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Pretendard", "Noto Sans KR", sans-serif; }}
main {{ max-width:720px; margin:0 auto; padding:16px 16px 48px; }}
h1 {{ font-size:22px; margin:4px 0 2px; }}
h2 {{ font-size:17px; margin:28px 0 10px; }}
h3 {{ font-size:14px; margin:16px 0 6px; color:var(--muted); }}
.sub {{ color:var(--muted); font-size:13px; }}
.summary {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:12px 14px; margin-top:14px; }}
.summary p {{ margin:4px 0; }}
.bench {{ display:flex; gap:14px; flex-wrap:wrap; font-size:13px; color:var(--muted); margin-top:10px; }}
.up {{ color:var(--up); }} .down {{ color:var(--down); }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:10px 12px; margin-bottom:8px; }}
.row1 {{ display:flex; align-items:center; gap:8px; }}
.rk {{ width:24px; height:24px; border-radius:6px; background:var(--line); display:grid; place-items:center; font-size:12px; font-weight:700; flex:none; }}
.nm {{ font-weight:700; flex:1; min-width:0; }}
.nm small {{ color:var(--muted); font-weight:400; }}
.mv {{ font-size:12px; color:var(--muted); }}
.stage {{ font-size:12px; padding:2px 8px; border-radius:999px; border:1px solid currentColor; flex:none; }}
.stage.lead {{ color:var(--lead); }} .stage.rise {{ color:var(--rise); }} .stage.cool {{ color:var(--cool); }} .stage.lag {{ color:var(--lag); }}
.row2 {{ display:flex; justify-content:space-between; align-items:center; gap:8px; margin-top:6px; }}
.nums {{ display:flex; gap:14px; }}
.nums label {{ display:block; font-size:11px; color:var(--muted); }}
.nums b {{ font-variant-numeric:tabular-nums; }}
.spark {{ flex:none; }}
.spark polyline {{ fill:none; stroke-width:1.6; }}
.spark.up polyline {{ stroke:var(--up); }} .spark.down polyline {{ stroke:var(--down); }}
.row3 {{ display:flex; flex-wrap:wrap; align-items:center; gap:6px; margin-top:6px; }}
.dot {{ font-size:11px; padding:1px 7px; border-radius:6px; background:var(--line); color:var(--muted); }}
.dot.on {{ background:var(--accent); color:#0f1115; font-weight:700; }}
.meta {{ font-size:12px; color:var(--muted); }}
details {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:10px 12px; margin-bottom:8px; }}
summary {{ cursor:pointer; font-weight:700; }}
summary small {{ color:var(--muted); font-weight:400; }}
.hold {{ list-style:none; padding:0; margin:8px 0 0; }}
.hold li {{ display:grid; grid-template-columns:62px 1fr 64px 64px; gap:6px; padding:4px 0; border-top:1px solid var(--line); font-size:13px; }}
.hold li.hd {{ border-top:0; color:var(--muted); font-size:11px; }}
.hold b {{ text-align:right; font-variant-numeric:tabular-nums; font-weight:600; }}
.tk {{ font-weight:700; }} .hn {{ color:var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.news {{ padding-left:18px; margin:0; }}
.news li {{ margin:4px 0; }}
.news a {{ color:var(--text); text-decoration:none; }}
.news small {{ color:var(--muted); margin-left:6px; }}
.how {{ font-size:13px; color:var(--muted); }}
.how b {{ color:var(--text); }}
.early {{ list-style:none; padding:0; margin:0 0 8px; }}
.early li {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:8px 12px; margin-bottom:6px; display:flex; flex-direction:column; gap:2px; }}
.early b {{ font-variant-numeric:tabular-nums; }}
</style>
</head>
<body>
<main>
<h1>미국 섹터·테마 트렌드</h1>
<div class="sub">{asof:%Y-%m-%d} 미국 종가 기준 · {built:%m월 %d일 %H:%M} KST 갱신</div>

<section class="summary">
{''.join(f'<p>{s}</p>' for s in summary)}
<div class="bench"><span>S&amp;P 500 1개월 <b class="{tone(spy1m)}">{pct(spy1m)}</b></span>
<span>3개월 <b class="{tone(spy3m)}">{pct(spy3m)}</b></span>
<span>나스닥100 1개월 <b class="{tone(qqq1m)}">{pct(qqq1m)}</b></span></div>
</section>

<h2>막 움직이기 시작한 테마</h2>
<div class="sub" style="margin:-6px 0 10px">가격보다 먼저 움직이는 경향이 있는 신호입니다. 앞으로 오른다는 뜻은 아니고, 헛신호도 많습니다.</div>
<h3>방향 전환 — 3개월간 S&amp;P보다 약했는데 최근 2주는 강함</h3>
{early_list(turn, "오늘은 해당 테마 없음")}
<h3>관심·거래 먼저 — 조회수나 거래대금은 늘었는데 1개월 가격은 아직 S&amp;P 이하</h3>
{early_list(buzz, "오늘은 해당 테마 없음")}

<h2>지금 강한 테마 순위</h2>
<div class="sub" style="margin:-6px 0 10px">숫자는 S&amp;P 500 대비 초과 수익률 · 선은 6개월 상대강도 · ▲▼는 1주 전 대비 순위</div>
{''.join(cards)}

<h2>상위 테마 대표 종목</h2>
{''.join(hold_html) or '<p class="sub">보유 종목 데이터를 가져오지 못했습니다.</p>'}

<h2>상위 테마 최근 뉴스 (3일)</h2>
{''.join(news_html) or '<p class="sub">뉴스를 가져오지 못했습니다.</p>'}

<h2>읽는 법</h2>
<div class="how">
<p><b>단계</b> — 3개월(그동안)과 2주(지금)를 S&amp;P와 비교. 주도: 둘 다 강함 / 떠오름: 3개월은 약했는데 2주는 강함 / 식는 중: 3개월은 강했는데 2주는 약함 / 소외: 둘 다 약함.</p>
<p><b>관심·거래·가격 표시</b> — 관심: 관련 위키백과 조회수가 최근 7일에 평소(그 전 8주)의 1.15배 이상 / 거래: 20일 거래대금이 120일 평균의 1.15배 이상 / 가격: 2주·1개월 모두 S&amp;P 초과. 셋 다 켜지면 말·돈·가격이 같은 방향.</p>
<p><b>점수</b> — 29개 테마 안에서의 백분위를 가중 평균(1개월 35%, 2주 20%, 3개월 20%, 거래 15%, 관심 10%). 최근 흐름을 빨리 잡도록 짧은 기간 비중을 높였고, 그만큼 순위가 자주 바뀌고 일시적 반등에도 흔들립니다. 절대 기준이 아니라 상대 순위입니다.</p>
<p><b>빠진 것</b> — 실적 전망 변화와 ETF 자금 유입은 무료 데이터가 없어 넣지 않았습니다. 관심도는 영어 위키 조회수라 대략적인 신호입니다.</p>
<p>지금 무엇이 주목받는지 보여주는 페이지일 뿐, 앞으로 오를 테마를 예측하거나 매매를 권하지 않습니다. 순위가 높을 때는 이미 많이 오른 뒤인 경우가 많습니다.</p>
<p>데이터: Yahoo Finance(가격·보유 종목), Wikimedia(조회수), Google 뉴스.</p>
</div>
</main>
</body>
</html>"""


# ---------- 실행 ----------

def main():
    etfs = [t[2] for t in THEMES]
    print("가격 수집…")
    close, volume = fetch_prices([BENCH[0], "QQQ"] + etfs)
    asof = close[BENCH[0]].dropna().index[-1]
    close, volume = close.loc[:asof], volume.loc[:asof]

    print("위키 조회수 수집…")
    wiki = {}
    for a in sorted({a for t in THEMES for a in t[3]}):
        wiki[a] = fetch_wiki(a)
        time.sleep(1.2)

    today = metrics(close, volume, wiki, -1)
    prev = metrics(close, volume, wiki, -1 - WEEK)

    print("보유 종목·뉴스 수집…")
    top = list(today.index[:8])
    raw = {tid: fetch_holdings(today.loc[tid, "etf"]) for tid in top}
    stocks = sorted({t for v in raw.values() for t, _ in v})
    holdings = {}
    if stocks:
        sc, _ = fetch_prices(stocks, period="6mo")
        for tid, items in raw.items():
            holdings[tid] = [(t, n, ret(sc[t], 21) if t in sc else np.nan, ret(sc[t], 63) if t in sc else np.nan)
                             for t, n in items]
    queries = {t[0]: t[4] for t in THEMES}
    news = {}
    for tid in top[:5]:
        news[tid] = fetch_news(queries[tid])
        time.sleep(1)

    built = datetime.now(KST)
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "index.html").write_text(render(today, prev, close, holdings, news, asof, built), encoding="utf-8")

    hist_path = ROOT / "data" / "history.json"
    hist_path.parent.mkdir(exist_ok=True)
    hist = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else {}
    hist[f"{asof:%Y-%m-%d}"] = {tid: {"rank": int(r["rank"]), "score": int(r.score),
                                       "rs2w": round(float(r.rs2w), 4), "rs1m": round(float(r.rs1m), 4),
                                       "rs3m": round(float(r.rs3m), 4),
                                       "attn": None if np.isnan(r.attn) else round(float(r.attn), 3)}
                                 for tid, r in today.iterrows()}
    hist_path.write_text(json.dumps(hist, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"완료: {asof:%Y-%m-%d} 기준, 1위 {today.iloc[0]['name']}")


if __name__ == "__main__":
    main()
