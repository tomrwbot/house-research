# House Research

Property research tools for Australian real estate analysis.

## Amenity Scorer

A standalone Python module that scores amenities for properties using free, open APIs.

### Features

- **Geocoding**: Convert addresses to coordinates using Nominatim (OpenStreetMap)
- **Amenity Discovery**: Find nearby schools, libraries, parks, cafes, supermarkets, restaurants, pharmacies, and doctors within configurable radius using Overpass API
- **Walking Distances**: Calculate actual walking distances and times using Open Route Service
- **Deduplication**: Automatic merging of duplicate amenities from overlapping queries
- **Structured Scoring**: Returns amenity type, distance, walking time, and count summaries
- **Zero Cost**: Uses only free APIs with no authentication required

### Supported Amenities

- Schools
- Libraries
- Parks
- Cafés
- Supermarkets
- Restaurants
- Pharmacies
- Doctors

### Installation

```bash
pip install -r requirements.txt
```

### Usage

#### Basic Example

```python
from scripts.amenity_scorer import AmenityScorer

scorer = AmenityScorer()
result = scorer.score_address("Sturt Street, Ballarat VIC, Australia")

if result:
    print(f"Location: {result.address}")
    print(f"Coordinates: {result.lat}, {result.lon}")
    
    for amenity_type, score_data in result.scoring.items():
        print(f"  {amenity_type}: {score_data['description']}")
    
    # Export to JSON
    json_output = scorer.to_json(result)
```

#### With Coordinates

If you already have coordinates:

```python
result = scorer.score_address(
    "My Property",
    lat=-37.5612,
    lon=143.8503,
    radius_m=1000  # 1km default
)
```

#### Output Structure

```json
{
  "address": "Sturt Street, Ballarat VIC, Australia",
  "lat": -37.5612,
  "lon": 143.8503,
  "timestamp": "2024-05-27T12:34:56.789012",
  "amenities_by_type": {
    "schools": [
      {
        "amenity_type": "school",
        "name": "Ballarat High School",
        "lat": -37.5600,
        "lon": 143.8500,
        "distance_m": 200.5,
        "walking_distance_m": 245.0,
        "walking_time_s": 176
      }
    ],
    "libraries": [...],
    "parks": [...]
  },
  "scoring": {
    "schools": {
      "count": 3,
      "avg_distance_m": 412.3,
      "avg_walking_time_s": 297,
      "nearest_m": 200.5,
      "description": "3 schools, nearest 200m (2min walk)"
    },
    "libraries": {
      "count": 0,
      "avg_distance_m": null,
      "avg_walking_time_s": null,
      "nearest_m": null,
      "description": "No libraries found"
    }
  }
}
```

### API Details

#### Free APIs Used

1. **Nominatim (OpenStreetMap)**
   - Purpose: Address geocoding
   - Rate limit: ~1 request/second recommended
   - Cost: Free
   - Usage: `NominatimGeocoder.geocode(address)`

2. **Overpass API (OpenStreetMap)**
   - Purpose: Find nearby amenities via OSM tags
   - Rate limit: Requested delays between amenity type queries
   - Cost: Free (but resource-intensive)
   - Usage: `OverpassAmenityFinder.find_amenities(lat, lon, radius_m)`

3. **Open Route Service**
   - Purpose: Calculate walking distances/times
   - Rate limit: Unknown (test first in non-production)
   - Cost: Free (community service)
   - Usage: `OpenRouteServiceRouter.calculate_walking_distances(...)`

### Data Quality Notes

- **Amenity accuracy**: Depends on OpenStreetMap data completeness
- **Walking distances**: More accurate than straight-line but may not account for actual paths/obstacles
- **Response times**: Nominatim typically 0.5–2s, Overpass 1–5s per amenity type, ORS varies with batch size
- **Radius limitations**: 1km default is a good balance; larger radius may cause ORS rate limiting

### Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=scripts --cov-report=html
```

### Project Structure

```
house-research/
├── scripts/
│   └── amenity_scorer.py       # Main module
├── tests/
│   └── test_amenity_scorer.py  # Unit & integration tests
├── requirements.txt            # Dependencies
├── setup.py                    # Package setup
└── README.md                   # This file
```

### Integration with House Research Scoring

Example integration:

```python
def property_amenity_score(address: str) -> dict:
    """Calculate amenity score for property scoring"""
    scorer = AmenityScorer()
    result = scorer.score_address(address)
    
    if not result:
        return {'status': 'error', 'message': 'Could not score amenities'}
    
    # Weighted scoring example
    weights = {
        'schools': 0.20,
        'libraries': 0.15,
        'parks': 0.15,
        'cafes': 0.10,
        'supermarkets': 0.15,
        'restaurants': 0.10,
        'pharmacies': 0.10,
        'doctors': 0.05
    }
    
    total_score = 0
    for amenity_type, weight in weights.items():
        count = result.scoring[amenity_type]['count']
        # Scoring: cap at 5 nearby as "excellent"
        amenity_score = min(count / 5.0, 1.0) * 100
        total_score += amenity_score * weight
    
    return {
        'status': 'success',
        'overall_score': round(total_score, 1),
        'breakdown': result.scoring,
        'coordinates': {'lat': result.lat, 'lon': result.lon}
    }
```

### Limitations & Future Improvements

- **ORS API**: Currently uses free hosted instance; may have reliability/rate-limit issues
- **Alternative routing**: Could integrate OSRM for faster batch routing
- **Offline mode**: Could cache OSM data for faster local queries
- **Custom amenities**: Could extend with user-defined POI searches
- **Weighting**: Different neighborhoods might value different amenities differently

### License

MIT

### Author

house-research project
