```markdown

\# Dutch VAT (BTW) \& KOR Guide



This document explains how VAT (BTW) and the Dutch KOR scheme are modeled inside the AI-Accountant-Orchestra project.  

The implementation is simplified and suitable for prototyping; always verify real-world rules using Belastingdienst documentation.



---



\## 1. VAT Rates Used in the Project



The project includes a demo VAT ruleset located at:



```



rules/nl\_vat\_2025.yaml



````



The configuration includes:



\- \*\*default\_rate:\*\* `0.21`  

\- \*\*low\_rate:\*\* `0.09`  

\- \*\*category\_rates:\*\* mapping from product category to VAT rate  

\- \*\*vat\_breakdown:\*\* computed summary of low/high buckets



Example breakdown in output:



```json

"vat\_breakdown": { "low": 5.20, "high": 9.00 }

````



These values are placeholders but match the general structure of Dutch VAT calculations.



---



\## 2. KOR (Kleineondernemersregeling)



The project includes a basic simulation of the KOR scheme.



\### Threshold



A business may apply for the KOR exemption if its \*\*annual gross revenue\*\* is below:



\*\*€20,000 per year\*\*



In the system:



```json

"kor\_applied": true

```



This occurs when:



```

summary.gross\_revenue < kor\_threshold

```



\### Effect



If KOR is applied:



\* VAT is \*\*not collected\*\*.

\* `tax\_amount` for all categories becomes `0`.

\* BTW return output reflects exemption.



This logic appears inside `tools/analysis/tax.py`.



---



\## 3. How the System Applies VAT Rules



1\. Data is loaded (CSV or other source via config).

2\. Each transaction receives a VAT rate:



&nbsp;  \* explicit `vat\_rate` column

&nbsp;  \* or inferred via `category\_rates`

&nbsp;  \* or fallback to `default\_rate`

3\. VAT is computed as:



```

tax\_amount = amount\_gross - (amount\_gross / (1 + rate))

```



4\. Summaries are aggregated by:



&nbsp;  \* category

&nbsp;  \* VAT bucket (low/high)

&nbsp;  \* full-period totals

5\. KOR overrides results if applicable.



---



\## 4. Outputs Relevant for Dutch Businesses



The system produces:



\* `summary\_latest.json`

\* VAT breakdowns

\* category-based subtotals

\* BTW period mappings (`Q1`, `Q2`, `Q3`, `Q4`)

\* CSV/JSON reports inside `workspace/reports/`



This allows small businesses to plug the framework directly into their bookkeeping pipeline by simply adjusting dataset paths.



---



\## 5. Real-World Accuracy Disclaimer



This implementation is:



\* suitable for learning

\* suitable for prototyping

\* \*\*not\*\* suitable for tax filing without manual verification



Always verify with official Belastingdienst sources or a certified accountant before using real transactional data.

