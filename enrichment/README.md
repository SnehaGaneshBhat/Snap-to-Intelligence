Person B — Enrichment, Standardization \& Conflict Resolution



\*\*Status: Core enrichment pipeline complete, tested with mock sources and edge cases, ready for integration.\*\*  

See `test\_merge.py` and `test\_edge\_cases.py` for validation runs — these confirm robustness against normal and edge scenarios.





Setup (do this first, \~15 min)



1\. Ensure Python 3.9+ is installed.  

2\. Install dependencies:  

&#x20;  ```bash

&#x20;  pip install -r requirements.txt

&#x20;  ```

&#x20;  (BeautifulSoup, requests, regex, dotenv, serpapi, etc.)  

3\. Add your SerpAPI key to `.env`:  

&#x20;  ```

&#x20;  SERPAPI\_KEY=your\_api\_key\_here

&#x20;  ```

4\. Verify you have Person A’s outputs locally (`/extraction` folder with JSON + test images).  

5\. Mock sources are stored in `/enrichment/test\_sources/` (breaker\_01, motor\_2 … motor\_8). Each contains:  

&#x20;  - `sources.txt`  

&#x20;  - Manufacturer datasheet  

&#x20;  - Distributor listing  





What's done



\- \[x] \*\*Search retrieval\*\* (`search\_test.py`) — queries SerpAPI for manufacturer/distributor pages.  

\- \[x] \*\*Spec extraction\*\* (`extract\_specs.py`) — parses raw text using regex + BeautifulSoup into structured fields.  

\- \[x] \*\*Unit normalization\*\* (`normalize.py`) — converts values into standard units (volts, amps, mm, kg, °C).  

\- \[x] \*\*Conflict resolution\*\* (`conflict\_resolution.py`) — authority ranking: manufacturer > datasheet > distributor > generic web. Logs disagreements in `conflicting\_values`.  

\- \[x] \*\*Confidence + completeness scoring\*\* (`scoring.py`) — assigns confidence based on source authority + agreement, computes completeness percentage, tracks missing fields.  

\- \[x] \*\*Merge logic\*\* (`merge.py`) — combines Person A’s extraction JSON with enrichment results into one schema‑compliant profile.  

\- \[x] \*\*Edge‑case handling\*\* (`test\_edge\_cases.py`) — tested “no web results” and “conflicting sources” scenarios.  

\- \[x] \*\*Validation tests\*\* (`test\_merge.py`) — confirmed normal merge works correctly.  





What Person C needs to know for integration



Import and call directly:



```python

from merge import build\_full\_profile



\# Example usage

final\_profile = build\_full\_profile(person\_a\_output, enrichment\_output)

```



\- \*\*Input:\*\*  

&#x20; - `person\_a\_output` → JSON from Person A’s `extract\_from\_image()`  

&#x20; - `enrichment\_output` → JSON from Person B’s enrichment functions  



\- \*\*Output:\*\*  

&#x20; Schema‑compliant product profile JSON with:  

&#x20; - Image filename  

&#x20; - Brand, model, serial  

&#x20; - Specs (enriched + normalized)  

&#x20; - Confidence + completeness score  

&#x20; - Missing fields  

&#x20; - Conflicting values  







Files in this folder



| File | Purpose |

|---|---|

| `search\_test.py` | Search + retrieval of manufacturer/distributor pages |

| `extract\_specs.py` | Parse raw text into structured specs |

| `normalize.py` | Unit standardization (volts, mm, kg, °C) |

| `conflict\_resolution.py` | Resolve disagreements across sources |

| `scoring.py` | Confidence + completeness scoring |

| `merge.py` | Final merge function — what Person C imports |

| `test\_merge.py` | Normal merge test with mock inputs |

| `test\_edge\_cases.py` | Edge‑case tests (no results, conflicts) |

| `test\_sources/` | Mock source files (breaker\_01, motor\_2 … motor\_8) |





Integration Notes



\- Person C wires the backend:  

&#x20; `POST /scan` → calls Person A’s `extract\_from\_image()` → passes result to Person B’s `build\_full\_profile()` → returns final JSON to frontend.  

\- Keys are stable and schema‑compliant.  

\- Tested standalone using mocks — safe to swap in Person A’s real outputs.  





Known Limitations

Source quality dependency — relies on manufacturer/distributor pages; incomplete data limits enrichment.

No live scraping guarantee — mock sources are stable, but live pages may change or break.

Scoped unit coverage — normalization rules cover only common units (volts, amps, mm/inches, kg/lbs, °C/°F).

Authority‑ranked conflict resolution — manufacturer prioritized; disagreements logged, not reconciled.

Heuristic confidence scoring — based on source authority and agreement, not statistical modeling.

Graceful edge‑case handling — products with no web presence marked "unverified" with empty specs.



