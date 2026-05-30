# Data Sources

This report uses FinanceDataReader and Bank of Korea ECOS data.

## Market and FX

| Label | Code | Source |
| --- | --- | --- |
| KOSPI | `KS11` | FinanceDataReader |
| KOSDAQ | `KQ11` | FinanceDataReader |
| USD/KRW | `USD/KRW` | FinanceDataReader |
| JPY/KRW | `JPY/KRW` | FinanceDataReader |
| CNY/KRW | `CNY/KRW` | FinanceDataReader |

## Rates

| Label | Code | Source |
| --- | --- | --- |
| US Treasury 10Y | `US10YT` | FinanceDataReader |
| US Treasury 20Y | `FRED:DGS20` | FinanceDataReader / FRED |
| US Treasury 30Y | `US30YT` | FinanceDataReader |
| Korea Treasury Bond 10Y | `ECOS:817Y002/010210000` | Bank of Korea ECOS |
| Korea Treasury Bond 20Y | `ECOS:817Y002/010220000` | Bank of Korea ECOS |
| Korea Treasury Bond 30Y | `ECOS:817Y002/010230000` | Bank of Korea ECOS |

For Korean Treasury bonds, the generator validates the ECOS response item names:

- `010210000` must return `국고채(10년)`
- `010220000` must return `국고채(20년)`
- `010230000` must return `국고채(30년)`

The workflow can run with the public ECOS sample key for the recent daily snapshot.
For a more durable production setup, add a repository secret named `BOK_API_KEY`.
