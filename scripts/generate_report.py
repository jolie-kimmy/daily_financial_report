from __future__ import annotations

import html
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import FinanceDataReader as fdr
import pandas as pd
import requests


KST = ZoneInfo("Asia/Seoul")
ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
REPORTS_DIR = DOCS_DIR / "reports"


@dataclass(frozen=True)
class MarketItem:
    name: str
    code: str
    category: str
    unit: str
    digits: int
    source: str = "fdr"
    expected_name: str | None = None


MARKET_ITEMS = [
    MarketItem("코스피", "KS11", "국내 증시", "pt", 2),
    MarketItem("코스닥", "KQ11", "국내 증시", "pt", 2),
    MarketItem("다우존스", "DJI", "미국 증시", "pt", 2),
    MarketItem("나스닥", "IXIC", "미국 증시", "pt", 2),
    MarketItem("S&P 500", "US500", "미국 증시", "pt", 2),
    MarketItem("러셀 2000", "RUT", "미국 증시", "pt", 2),
    MarketItem("원/달러", "USD/KRW", "환율", "KRW", 2),
    MarketItem("원/엔", "JPY/KRW", "환율", "KRW", 2),
    MarketItem("원/위안", "CNY/KRW", "환율", "KRW", 2),
    MarketItem("미국채 10년", "US10YT", "금리", "%", 3),
    MarketItem("미국채 20년", "FRED:DGS20", "금리", "%", 3),
    MarketItem("미국채 30년", "US30YT", "금리", "%", 3),
    MarketItem("국고채 10년", "010210000", "금리", "%", 3, "ecos", "국고채(10년)"),
    MarketItem("국고채 20년", "010220000", "금리", "%", 3, "ecos", "국고채(20년)"),
    MarketItem("국고채 30년", "010230000", "금리", "%", 3, "ecos", "국고채(30년)"),
]


def money(value: float | int | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.{digits}f}"


def signed(value: float | int | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):+,.{digits}f}"


def percent(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) * 100:+.2f}%"


def direction_class(value: object) -> str:
    if isinstance(value, float) and value > 0:
        return "up"
    if isinstance(value, float) and value < 0:
        return "down"
    return "flat"


def category_class(category: object) -> str:
    mapping = {
        "국내 증시": "domestic",
        "미국 증시": "us-market",
        "환율": "fx",
        "금리": "rates",
    }
    return mapping.get(str(category), "general")


def fetch_fdr_item(item: MarketItem, today: datetime) -> dict[str, object]:
    start = (today - timedelta(days=21)).strftime("%Y-%m-%d")
    end = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    df = fdr.DataReader(item.code, start, end)

    if df.empty:
        raise RuntimeError(f"No data returned for {item.name} ({item.code})")

    df = df.sort_index()
    value_column = "Close" if "Close" in df.columns else df.columns[0]
    latest = df.iloc[-1]
    previous = df.iloc[-2] if len(df) > 1 else None
    latest_value = float(latest[value_column])
    previous_value = float(previous[value_column]) if previous is not None else None
    change = latest_value - previous_value if previous_value is not None else None
    change_rate = change / previous_value if previous_value else None

    return {
        "name": item.name,
        "code": item.code,
        "category": item.category,
        "unit": item.unit,
        "digits": item.digits,
        "date": df.index[-1].strftime("%Y-%m-%d"),
        "close": latest_value,
        "change": change,
        "change_rate": change_rate,
        "source": "FinanceDataReader",
        "verified_name": item.expected_name or item.name,
    }


def fetch_ecos_item(item: MarketItem, today: datetime) -> dict[str, object]:
    api_key = os.environ.get("BOK_API_KEY") or "sample"
    start = (today - timedelta(days=10)).strftime("%Y%m%d")
    end = (today + timedelta(days=1)).strftime("%Y%m%d")
    url = (
        "https://ecos.bok.or.kr/api/StatisticSearch/"
        f"{api_key}/json/kr/1/10/817Y002/D/{start}/{end}/{item.code}"
    )
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    payload = response.json()

    rows = payload.get("StatisticSearch", {}).get("row", [])
    if not rows:
        raise RuntimeError(f"No ECOS data returned for {item.name} ({item.code})")

    rows = sorted(rows, key=lambda row: row["TIME"])
    latest = rows[-1]
    previous = rows[-2] if len(rows) > 1 else None
    verified_name = latest.get("ITEM_NAME1", "")
    if item.expected_name and verified_name != item.expected_name:
        raise RuntimeError(
            f"Unexpected ECOS item for {item.name}: {verified_name} != {item.expected_name}"
        )

    latest_value = float(latest["DATA_VALUE"])
    previous_value = float(previous["DATA_VALUE"]) if previous else None
    change = latest_value - previous_value if previous_value is not None else None
    change_rate = change / previous_value if previous_value else None

    return {
        "name": item.name,
        "code": f"ECOS:817Y002/{item.code}",
        "category": item.category,
        "unit": item.unit,
        "digits": item.digits,
        "date": datetime.strptime(latest["TIME"], "%Y%m%d").strftime("%Y-%m-%d"),
        "close": latest_value,
        "change": change,
        "change_rate": change_rate,
        "source": "한국은행 ECOS",
        "verified_name": verified_name,
    }


def fetch_market_item(item: MarketItem, today: datetime) -> dict[str, object]:
    if item.source == "ecos":
        return fetch_ecos_item(item, today)
    return fetch_fdr_item(item, today)


def build_rows(items: list[dict[str, object]]) -> str:
    rows = []
    for item in items:
        direction = direction_class(item["change"])
        rows.append(
            f"""
            <tr>
              <td>
                <strong>{html.escape(str(item["name"]))}</strong>
                <span>{html.escape(str(item["code"]))}</span>
              </td>
              <td>{html.escape(str(item["category"]))}</td>
              <td>{html.escape(str(item["date"]))}</td>
              <td>{html.escape(str(item["source"]))}</td>
              <td class="number">{money(item["close"], int(item["digits"]))} {html.escape(str(item["unit"]))}</td>
              <td class="number {direction}">{signed(item["change"], int(item["digits"]))}</td>
              <td class="number {direction}">{percent(item["change_rate"])}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def build_cards(items: list[dict[str, object]]) -> str:
    cards = []
    for item in items:
        direction = direction_class(item["change"])
        label = "보합"
        if direction == "up":
            label = "상승"
        elif direction == "down":
            label = "하락"

        cards.append(
            f"""
            <article class="metric {category_class(item["category"])}">
              <div>
                <p>{html.escape(str(item["category"]))}</p>
                <h2>{html.escape(str(item["name"]))}</h2>
              </div>
              <strong>{money(item["close"], int(item["digits"]))}</strong>
              <span class="{direction}">{label} {percent(item["change_rate"])}</span>
            </article>
            """
        )
    return "\n".join(cards)


def render_html(items: list[dict[str, object]], generated_at: datetime) -> str:
    rows = build_rows(items)
    cards = build_cards(items)
    date_label = generated_at.strftime("%Y년 %m월 %d일 %H:%M KST")
    latest_data_date = max(str(item["date"]) for item in items)
    market_count = len(items)

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Daily Financial Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f3f5f7;
      --panel: #ffffff;
      --ink: #182230;
      --muted: #667085;
      --line: #d9e0ea;
      --up: #b42318;
      --down: #175cd3;
      --flat: #475467;
      --brand: #24537a;
      --teal: #08756f;
      --gold: #b7791f;
      --header: #132238;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        linear-gradient(180deg, #edf1f5 0, #f8fafc 320px, var(--bg) 100%);
      color: var(--ink);
      font-family: Arial, "Noto Sans KR", sans-serif;
      line-height: 1.5;
    }}
    main {{
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 40px 0;
    }}
    header {{
      background: var(--header);
      color: #ffffff;
      border: 1px solid #223653;
      border-radius: 8px;
      margin-bottom: 20px;
      padding: 28px;
      box-shadow: 0 16px 40px rgba(20, 35, 56, 0.16);
      position: relative;
      overflow: hidden;
    }}
    header::before {{
      content: "";
      position: absolute;
      inset: 0 0 auto;
      height: 5px;
      background: linear-gradient(90deg, #2f80ed, #12b76a, #f2c94c, #eb5757);
    }}
    .header-grid {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 24px;
      align-items: end;
      position: relative;
      z-index: 1;
    }}
    header p {{
      color: #c8d3df;
      margin: 8px 0 0;
    }}
    h1 {{
      font-size: clamp(28px, 4vw, 44px);
      line-height: 1.1;
      margin: 0;
      letter-spacing: 0;
    }}
    .meta-panel {{
      display: grid;
      grid-template-columns: repeat(2, minmax(110px, 1fr));
      gap: 10px;
      min-width: 280px;
    }}
    .meta {{
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.16);
      border-radius: 8px;
      padding: 12px;
    }}
    .meta span {{
      color: #9fb1c5;
      display: block;
      font-size: 12px;
    }}
    .meta strong {{
      color: #ffffff;
      display: block;
      font-size: 18px;
      margin-top: 2px;
    }}
    .badge-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 18px;
    }}
    .badge {{
      background: #f2f4f7;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: #344054;
      font-size: 12px;
      font-weight: 700;
      padding: 6px 10px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 14px;
      margin-bottom: 22px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      border-top: 4px solid var(--brand);
      padding: 17px;
      min-height: 150px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      box-shadow: 0 10px 28px rgba(24, 34, 48, 0.08);
    }}
    .metric.domestic {{ border-top-color: var(--brand); }}
    .metric.us-market {{ border-top-color: #6941c6; }}
    .metric.fx {{ border-top-color: var(--teal); }}
    .metric.rates {{ border-top-color: var(--gold); }}
    .metric:hover {{
      transform: translateY(-1px);
      transition: transform 140ms ease, box-shadow 140ms ease;
      box-shadow: 0 14px 32px rgba(24, 34, 48, 0.12);
    }}
    .metric p {{
      color: var(--muted);
      font-size: 13px;
      margin: 0 0 4px;
    }}
    .metric h2 {{
      font-size: 17px;
      margin: 0;
    }}
    .metric strong {{
      font-size: 25px;
      letter-spacing: 0;
    }}
    .metric span {{
      font-weight: 700;
      width: fit-content;
      border-radius: 999px;
      background: #f8fafc;
      padding: 5px 9px;
    }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th, td {{
      padding: 15px 18px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: middle;
    }}
    th {{
      background: #eef3f7;
      color: #344054;
      font-size: 13px;
      font-weight: 700;
    }}
    tbody tr:hover {{ background: #fafcff; }}
    td span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-top: 2px;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    .number {{
      font-variant-numeric: tabular-nums;
      text-align: right;
      white-space: nowrap;
    }}
    .up {{ color: var(--up); }}
    .down {{ color: var(--down); }}
    .flat {{ color: var(--flat); }}
    footer {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 18px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    footer a {{ color: var(--brand); }}
    @media (max-width: 920px) {{
      .header-grid {{ grid-template-columns: 1fr; }}
      .meta-panel {{ min-width: 0; }}
      section {{ overflow-x: auto; }}
      table {{ min-width: 920px; }}
    }}
    @media (max-width: 560px) {{
      main {{ width: min(100% - 20px, 1180px); padding: 24px 0; }}
      th, td {{ padding: 12px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="header-grid">
        <div>
          <h1>Daily Financial Report</h1>
        </div>
        <div class="meta-panel" aria-label="리포트 메타 정보">
          <div class="meta">
            <span>생성 시각</span>
            <strong>{html.escape(date_label)}</strong>
          </div>
          <div class="meta">
            <span>최신 기준일</span>
            <strong>{html.escape(latest_data_date)}</strong>
          </div>
          <div class="meta">
            <span>추적 지표</span>
            <strong>{market_count}개</strong>
          </div>
          <div class="meta">
            <span>업데이트</span>
            <strong>매일 10:00</strong>
          </div>
        </div>
      </div>
    </header>
    <div class="badge-row" aria-label="데이터 출처">
      <span class="badge">FinanceDataReader</span>
      <span class="badge">FRED</span>
      <span class="badge">한국은행 ECOS</span>
    </div>
    <div class="summary">
      {cards}
    </div>
    <section aria-label="시황 상세 표">
      <table>
        <thead>
          <tr>
            <th>지표</th>
            <th>구분</th>
            <th>기준일</th>
            <th>출처</th>
            <th class="number">종가/금리</th>
            <th class="number">전일 대비</th>
            <th class="number">등락률</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </section>
    <footer>
      Generated from <a href="https://github.com/FinanceData/FinanceDataReader">FinanceDataReader</a>
      and <a href="https://ecos.bok.or.kr">Bank of Korea ECOS</a>.
      This report is for informational use only.
    </footer>
  </main>
</body>
</html>
"""


def main() -> None:
    generated_at = datetime.now(KST)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    items = [fetch_market_item(item, generated_at) for item in MARKET_ITEMS]
    document = render_html(items, generated_at)

    report_path = REPORTS_DIR / f"{generated_at:%Y-%m-%d}.html"
    index_path = DOCS_DIR / "index.html"
    report_path.write_text(document, encoding="utf-8")
    shutil.copyfile(report_path, index_path)
    print(f"Wrote {report_path.relative_to(ROOT)}")
    print(f"Wrote {index_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
