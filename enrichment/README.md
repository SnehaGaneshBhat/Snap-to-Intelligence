Person B — Enrichment, Standardization \& Conflict Resolution

\*\*Status: Core enrichment pipeline complete, tested with mock sources and edge cases, ready for integration.\*\*  
See `test\_merge.py` and `test\_edge\_cases.py` for validation runs — these confirm robustness against normal and edge scenarios.

## Setup (do this first, ~15 min)

1. Ensure Python 3.9+ is installed.  
2. Install dependencies:  
   ```bash
   pip install -r requirements.txt
   ```
   *(BeautifulSoup, requests, regex, dotenv, serpapi, etc.)*  
3. Add your SerpAPI key to `.env`:  
   ```
   SERPAPI_KEY=your_api_key_here
   ```
4. Verify you have Person A’s outputs locally (`/extraction` folder with JSON + test images).  
5. Mock sources are stored in `/enrichment/test_sources/` (breaker_01, motor_2 … motor_8). Each contains:  
   - `sources.txt`  
   - Manufacturer datasheet  
   - Distributor listing  

What's done

 \*\*Search retrieval\*\* (`search\_test.py`) — queries SerpAPI for manufacturer/distributor pages.  
 \*\*Spec extraction\*\* (`extract\_specs.py`) — parses raw text using regex + BeautifulSoup into structured fields.  
 \*\*Unit normalization\*\* (`normalize.py`) — converts values into standard units (volts, amps, mm, kg, °C).  
 \*\*Conflict resolution\*\* (`conflict\_resolution.py`) — authority ranking: manufacturer > datasheet > distributor > generic web. Logs disagreements in `conflicting\_values`.  
 \*\*Confidence + completeness scoring\*\* (`scoring.py`) — assigns confidence based on source authority + agreement, computes completeness percentage, tracks missing fields.  
 \*\*Merge logic\*\* (`merge.py`) — combines Person A’s extraction JSON with enrichment results into one schema‑compliant profile.  
 \*\*Edge‑case handling\*\* (`test\_edge\_cases.py`) — tested “no web results” and “conflicting sources” scenarios.  
 \*\*Validation tests\*\* (`test\_merge.py`) — confirmed normal merge works correctly.  

## What Person C Needs to Know for Integration
Import and call directly:
```python
from merge import build_full_profile

# Example usage
final_profile = build_full_profile(person_a_output, enrichment_output)
```

**Input:**  
- `person_a_output` → JSON from Person A’s `extract_from_image()`  
- `enrichment_output` → JSON from Person B’s enrichment functions  

**Output:**  
Schema‑compliant product profile JSON with:  
- Image filename  
- Brand, model, serial  
- Specs (enriched + normalized)  
- Confidence + completeness score  
- Missing fields  
- Conflicting values  

Files in this folder

| File | Purpose |

| `search\_test.py`           
Search + retrieval of manufacturer/distributor pages |

| `extract\_specs.py`         
Parse raw text into structured specs |

| `normalize.py`              
Unit standardization (volts, mm, kg, °C) |

| `conflict\_resolution.py`   
Resolve disagreements across sources |

| `scoring.py`                
Confidence + completeness scoring |

| `merge.py`                 
Final merge function — what Person C imports |

| `test\_merge.py`           
Normal merge test with mock inputs |

| `test\_edge\_cases.py`      
Edge‑case tests (no results, conflicts) |

| `test\_sources/`           
Mock source files (breaker\_01, motor\_2 … motor\_8) |

## Shared Folder

The `/shared` directory contains the schema contract and mock data used across all components:

- **`schema.json`**  
  - Defines the canonical product profile schema  
  - Keys are stable and must not be changed without team consensus  
  - Used by Person A (extraction), Person B (enrichment), and Person C (frontend)  

- **`mocks/mock_products.json`**  
  - Contains sample product profiles for testing and UI development  
  - Used by Person C to build the frontend before real backend integration  
  - Used by Person B to validate enrichment logic against schema compliance  
  - Provides a safe dataset when live scraping is unavailable  

Integration Notes

\- Person C wires the backend:
 `POST /scan` → calls Person A’s `extract\_from\_image()` → passes result to Person B’s `build\_full\_profile()` → returns final JSON to frontend.  
\- Keys are stable and schema‑compliant.  
\- Tested standalone using mocks — safe to swap in Person A’s real outputs.  

## Known Limitations

- **Source quality dependency** — relies on manufacturer/distributor pages; incomplete data limits enrichment  
- **No live scraping guarantee** — mock sources are stable, but live pages may change or break  
- **Scoped unit coverage** — normalization rules cover only common units (volts, amps, mm/inches, kg/lbs, °C/°F)  
- **Authority‑ranked conflict resolution** — manufacturer prioritized; disagreements logged, not reconciled  
- **Heuristic confidence scoring** — based on source authority and agreement, not statistical modeling  
- **Graceful edge‑case handling** — products with no web presence marked `"unverified"` with empty specs  


