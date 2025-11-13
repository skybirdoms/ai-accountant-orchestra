# BTW Summary

_Run date:_ **{{ today or run_date or generation_date or "" }}**  
_Period:_ **{{ period or (params and params.period) or "N/A" }}**

## Overview
- **Transactions:** {{ summary.n_transactions or 0 }}
- **Gross revenue:** {{ "%.2f"|format((summary.gross_revenue or 0)|float) }}
- **Net revenue:** {{ "%.2f"|format((summary.net_revenue or 0)|float) }}

## Returns
- **Count:** {{ (summary.returns.n if summary.returns else 0) }}
- **Sum:** {{ "%.2f"|format(((summary.returns.sum) if summary.returns else 0)|float) }}

## VAT Breakdown
- **Low VAT (9%)**: {{ "%.2f"|format(((vat_breakdown.low) if vat_breakdown else 0)|float) }}
- **High VAT (21%)**: {{ "%.2f"|format(((vat_breakdown.high) if vat_breakdown else 0)|float) }}

## KOR Status
{% if kor_applied %}Kleineondernemersregeling (KOR) applied: YES{% else %}Kleineondernemersregeling (KOR) applied: NO{% endif %}
