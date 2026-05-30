from __future__ import annotations

import html
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import FinanceDataReader as fdr
import pandas as pd


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


MARKET_ITEMS = [
    MarketItem("코스피", "KS11", "국내 증시", "pt", 2),
    MarketItem("코스닥", "KQ11", "국내 증시", "pt", 2),
    MarketItem("원/달러", "USD/KRW", "환율", "KRW", 2),
    MarketItem("원/엔", "JPY/KRW", "환율", "KRW", 2),
    MarketItem("원/위안", "CNY/KRW", "환율", "KRW", 2),
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


def fetch_market_item(item: MarketItem, today: datetime) -> dict[str, object]:
    start = (today - timedelta(days=21)).strftime("%Y-%m-%d")
    end = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    df = fdr.DataReader(item.code, start, end)

    if df.empty:
        raise RuntimeError(f"No data returned for {item.name} ({item.code})")

    df = df.sort_index()
    latest = df.iloc[-1]
    previous = df.iloc[-2] if len(df) > 1 else None
    latest_close = float(latest["Close"])
    previous_close = float(previous["Close"]) if previous is not None else None
    change = latest_close - previous_close if previous_close is not None else None
    change_rate = change / previous_close if previous_close else None

    return {
        "name": item.name,
        "code": item.code,
        "category": item.category,
        "unit": item.unit,
        "digits": item.digits,
        "date": df.index[-1].strftime("%Y-%m-%d"),
        "close": latest_close,
        "change": change,
        "change_rate": change_rate,
        "open": latest.get("Open"),
        "high": latest.get("High"),
        "low": latest.get("Low"),
        "volume": latest.get("Volume"),
    }


def build_rows(items: list[dict[str, object]]) -> str:
    rows = []
    for item in items:
        change = item["change"]
        direction = "flat"
        if isinstance(change, float) and change > 0:
            direction = "up"
        elif isinstance(change, float) and change < 0:
            direction = "down"

        rows.append(
            f"""
            <tr>
              <td>
                <strong>{html.escape(str(item["name"]))}</strong>
                <span>{html.escape(str(item["code"]))}</span>
              </td>
              <td>{html.escape(str(item["category"]))}</td>
              <td>{html.escape(str(item["date"]))}</td>
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
        change = item["change"]
        direction = "flat"
        label = "보합"
        if isinstance(change, float) and change > 0:
            direction = "up"
            label = "상승"
        elif isinstance(change, float) and change < 0:
            direction = "down"
            label = "하락"

        cards.append(
            f"""
            <article class="metric">
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

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Daily Financial Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #172033;
      --muted: #667085;
      --line: #d8dee8;
      --up: #b42318;
      --down: #175cd3;
      --flat: #475467;
      --brand: #1f4e79;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Arial, "Noto Sans KR", sans-serif;
      line-height: 1.5;
    }}
    main {{
      width: min(1120px, calc(100% - 32px));
      margin: 0 auto;
      padding: 40px 0;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      margin-bottom: 24px;
      padding-bottom: 20px;
    }}
    header p {{
      color: var(--muted);
      margin: 8px 0 0;
    }}
    h1 {{
      font-size: clamp(28px, 4vw, 44px);
      line-height: 1.1;
      margin: 0;
      letter-spacing: 0;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 24px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      min-height: 158px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
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
      background: #eef3f8;
      color: #29435c;
      font-size: 13px;
      font-weight: 700;
    }}
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
    }}
    footer a {{ color: var(--brand); }}
    @media (max-width: 920px) {{
      .summary {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      section {{ overflow-x: auto; }}
      table {{ min-width: 760px; }}
    }}
    @media (max-width: 560px) {{
      main {{ width: min(100% - 20px, 1120px); padding: 24px 0; }}
      .summary {{ grid-template-columns: 1fr; }}
      th, td {{ padding: 12px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Daily Financial Report</h1>
      <p>생성 시각: {html.escape(date_label)} · 데이터 출처: FinanceDataReader</p>
    </header>
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
            <th class="number">종가</th>
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
      Generated from <a href="https://github.com/FinanceData/FinanceDataReader">FinanceDataReader</a>.
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
