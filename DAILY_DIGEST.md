# Daily Digest Pipeline

## Overview

The daily digest pipeline automates amenity scoring for properties and generates a formatted summary report. It runs unattended at **6:30 AM AWST** and caches amenity data to minimize API calls.

## Features

### ✨ Daily Digest Generation
- Loads properties from `properties.json`
- Scores each property using the amenity scorer
- Ranks properties by amenity quality (0-100 score)
- Generates formatted, human-readable digest
- Includes detailed amenity breakdowns

### 📊 Weighted Amenity Scoring

Each property receives a score 0-100 based on nearby amenities:

| Amenity Type | Weight | Description |
|---|---|---|
| Schools | 20% | Critical for families |
| Libraries | 10% | Community & education |
| Parks | 15% | Recreation & green space |
| Cafes | 10% | Social venues |
| Supermarkets | 15% | Essential services |
| Restaurants | 10% | Dining options |
| Pharmacies | 10% | Health services |
| Doctors | 10% | Medical access |

**Scoring Logic:** 5+ nearby amenities of a type = 100 pts (excellent), scales linearly.

### 🔄 Smart Caching

- Amenity data cached in `properties.json`
- Fresh data reused for 7 days (avoids API hammering)
- Automatic cache invalidation after 7 days
- Reduces API load by ~95% in typical usage

## Installation

### Prerequisites

```bash
pip install -r requirements.txt
```

### Properties File

Create `properties.json` in the repo root:

```json
{
  "properties": [
    {
      "id": "property_001",
      "address": "123 Main Street, Ballarat VIC 3350",
      "lat": -37.5650,
      "lon": 143.8450,
      "price_aud": 520000,
      "bedrooms": 4,
      "bathrooms": 2,
      "land_area_sqm": 600,
      "year_built": 2005,
      "amenity_data": null
    }
  ],
  "last_digest": null,
  "digest_frequency": "daily",
  "digest_time_awst": "06:30"
}
```

## Usage

### Manual Digest Generation

**With mock data (for testing):**
```bash
python3 scripts/daily_digest.py --mock
```

**With real APIs (production):**
```bash
python3 scripts/daily_digest.py
```

### Scheduled Execution (Cron)

For 6:30 AM AWST (UTC+8):

```bash
30 22 * * * cd /path/to/house-research && python3 scripts/daily_digest.py >> logs/digest.log 2>&1
```

*Note: 22:30 UTC = 6:30 AWST (previous day)*

### Example Output

```
================================================================================
HOUSE RESEARCH DAILY DIGEST
Generated: 2026-05-27T21:45:01.955341
================================================================================

[1] Main Road, Ballarat VIC 3350, Australia
    ────────────────────────────────────────────────────────────────────────────
    Price: $520,000 AUD | 4BR / 2BA | Amenity Score: 66.0/100

    Nearby Amenities:
      • 4 schools, nearest 150m (107min walk)
      • 3 parks, nearest 150m (107min walk)
      • 7 cafes, nearest 150m (107min walk)
      • 2 libraries, nearest 150m (107min walk)
      • 3 supermarkets, nearest 150m (107min walk)

    Details: 600m² | Built 2005

================================================================================
SUMMARY
================================================================================
Total Properties: 1
Average Amenity Score: 66.0/100
```

## Architecture

### Components

1. **DigestGenerator** (`daily_digest.py`)
   - Loads properties from JSON
   - Orchestrates amenity scoring
   - Manages caching logic
   - Generates formatted output

2. **AmenityScorer** (`amenity_scorer.py`)
   - Geocodes addresses → Nominatim
   - Finds amenities → Overpass API
   - Calculates walking distances → ORS
   - Generates scoring & summaries

3. **Data Flow**
```
properties.json
    ↓
DigestGenerator.load_properties()
    ↓
Score each property (check cache first)
    ↓
Calculate weighted amenity scores
    ↓
Generate formatted digest
    ↓
Save updated properties.json (with cache)
    ↓
Output to stdout
```

## API Usage

### Free APIs Used

1. **Nominatim** (OpenStreetMap)
   - Geocoding: address → lat/lon
   - Rate limit: ~1 req/s recommended
   - No authentication required

2. **Overpass API** (OpenStreetMap)
   - Amenity discovery via OSM tags
   - Searches within 1km radius
   - Rate limit: Request delays between queries
   - No authentication required

3. **Open Route Service**
   - Walking distance/time calculation
   - Free community instance
   - Rate limit: Unknown (test first)
   - No authentication required

## Testing

Run the complete test suite:

```bash
python3 -m pytest tests/ -v
```

Individual test modules:

```bash
# Amenity scorer tests (17 tests)
pytest tests/test_amenity_scorer.py -v

# Daily digest tests (10 tests)
pytest tests/test_daily_digest.py -v
```

### Test Coverage

- ✅ Property loading/saving
- ✅ Amenity scoring with mock data
- ✅ Cache logic (fresh/stale data)
- ✅ Digest generation & formatting
- ✅ Weighted scoring calculations
- ✅ Property ranking by amenity score
- ✅ End-to-end pipeline

All 27 tests passing.

## Configuration

### Modify Weights

Edit `_enhance_property_with_scores()` in `daily_digest.py`:

```python
weights = {
    'schools': 0.25,      # Increase weight
    'libraries': 0.10,
    'parks': 0.15,
    # ... etc
}
```

### Extend Amenity Types

Edit `AMENITY_TYPES` in `amenity_scorer.py`:

```python
AMENITY_TYPES = {
    'gyms': 'leisure=fitness_centre',
    'schools': 'amenity=school',
    # ... add more
}
```

### Change Search Radius

Default is 1km. Modify in `daily_digest.py`:

```python
result = self.scorer.score_address(
    address=address,
    lat=lat,
    lon=lon,
    radius_m=2000  # 2km instead of 1km
)
```

## Troubleshooting

### API Errors

If Overpass/ORS APIs are down:
- Digest uses `--mock` mode automatically for testing
- Install caching will reuse previous results
- Manual API testing: `python3 examples/ballarat_scoring_example.py`

### Slow Performance

- **First run:** All properties require API calls (~30-60s for 3 properties)
- **Subsequent runs:** Cache hit speeds up to <1s per property
- If APIs are slow: Check rate limiting, wait, retry

### Missing Amenities

Amenity data depends on OpenStreetMap completeness. To improve:
1. Verify OSM data at [openstreetmap.org](https://openstreetmap.org)
2. Add missing amenities via OSM editor
3. Wait for Overpass cache refresh (~1 hour)

## Next Steps

Potential improvements:

- [ ] Email notifications with digest summary
- [ ] Historical trend analysis (score changes over time)
- [ ] Custom amenity weighting per neighborhood
- [ ] Integration with property valuation model
- [ ] Web dashboard for digest history
- [ ] Alert system for properties dropping below threshold
- [ ] Comparable sales analysis based on amenity scores

## Files

- `scripts/daily_digest.py` - Main pipeline (360 lines)
- `scripts/amenity_scorer.py` - Amenity scoring module (enhanced)
- `properties.json` - Property database with cache
- `tests/test_daily_digest.py` - Test suite (10 tests)

## License

MIT
