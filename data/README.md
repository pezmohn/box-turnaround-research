# Data

Raw and processed market data should stay local and is gitignored.

Recommended layout:

```text
data/raw/          original vendor exports
data/interim/      normalized/resampled intermediate data
data/processed/    event datasets generated from confirmed box logic
```

Commit only small synthetic samples if needed for tests. Do not commit licensed market data.
