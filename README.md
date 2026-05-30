# daily_financial_report

Daily Korean market snapshot generated with
[FinanceDataReader](https://github.com/FinanceData/FinanceDataReader).

The report is generated every day at 10:00 KST by GitHub Actions.

## Outputs

- Latest report: `docs/index.html`
- Daily archive: `docs/reports/YYYY-MM-DD.html`

## Run locally

```bash
pip install -r requirements.txt
python scripts/generate_report.py
```
