# Baseline Agent Report

- candidate: `phase3-after`
- base: `phase2-after`
- conclusion: `PASS`
- generated_at: `2026-05-16T22:51:12+08:00`

## Reasons

- no blocking issue

## Symbols

- `NVDA.US`: ok; refreshed=False; mode=none; warnings=data already fresh; refresh skipped
- `0700.HK`: ok; refreshed=False; mode=none; warnings=data already fresh; refresh skipped
- `600900.SH`: ok; refreshed=False; mode=none; warnings=data already fresh; refresh skipped

## Refresh

- targets: `none`

## Pre Data Gate

- returncode: `0`

```text
============================================================
数据门禁校验结果
阈值：{'1h': '4h', '1d': '24h', '1w': '192h'} [仅关键数据]
============================================================
总标的数：3
通过：3
未通过：0

✅ PASS — 所有标的数据均为最新
```

## Data Gate

- returncode: `0`

```text
============================================================
数据门禁校验结果
阈值：{'1h': '4h', '1d': '24h', '1w': '192h'} [仅关键数据]
============================================================
总标的数：3
通过：3
未通过：0

✅ PASS — 所有标的数据均为最新
```

## Baseline Summary

- `NVDA.US`: ok warnings=0
- `0700.HK`: ok warnings=0
- `600900.SH`: ok warnings=0

## Regression

- status: `ok`
- regressions: `0`
- improvements: `0`
