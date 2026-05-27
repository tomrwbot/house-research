"""
Amenity Scoring Integration for Australian Properties

Uses free APIs:
- Nominatim (OpenStreetMap): Geocoding
- Overpass API (OpenStreetMap): Amenity discovery
- Open Route Service: Walking distance/time calculation

Author: house-research
License: MIT
"""

import json
import logging
import time
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime
import requests
from urllib.parse import urlencode

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class AmenityPoint:
    """Represents a single amenity location"""
    amenity_type: str
    name: Optional[str]
    lat: float
    lon: float
    distance_m: Optional[float] = None  # Straight-line distance
    walking_distance_m: Optional[float] = None
    walking_time_s: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AmenitySummary:
    """Summary of amenities for a location"""
    address: str
    lat: float
    lon: float
    timestamp: str
    amenities_by_type: Dict[str, List[AmenityPoint]]
    scoring: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'address': self.address,
            'lat': self.lat,
            'lon': self.lon,
            'timestamp': self.timestamp,
            'amenities_by_type': {
                k: [a.to_dict() for a in v]
                for k, v in self.amenities_by_type.items()
            },
            'scoring': self.scoring
        }


class NominatimGeocoder:
    """Geocoding via Nominatim (OpenStreetMap)"""
    
    BASE_URL = "https://nominatim.openstreetmap.org"
    
    def __init__(self, user_agent: str = "house-research-amenity-scorer/1.0"):
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers['User-Agent'] = user_agent
    
    def geocode(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Geocode an address to lat/lon
        Returns: (lat, lon) or None if not found
        """
        try:
            params = {
                'q': address,
                'format': 'json',
                'limit': 1
            }
            response = self.session.get(
                f"{self.BASE_URL}/search",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
            return None
        except Exception as e:
            logger.error(f"Geocoding failed for '{address}': {e}")
            return None


class OverpassAmenityFinder:
    """Find amenities via Overpass API (OpenStreetMap)"""
    
    BASE_URL = "https://overpass-api.de/api/interpreter"
    
    # Amenity tags to search for within 1km radius
    AMENITY_TYPES = {
        'schools': 'amenity=school',
        'libraries': 'amenity=library',
        'parks': 'leisure=park',
        'cafes': 'amenity=cafe',
        'supermarkets': 'shop=supermarket',
        'restaurants': 'amenity=restaurant',
        'pharmacies': 'amenity=pharmacy',
        'doctors': 'amenity=doctors'
    }
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'house-research-amenity-scorer/1.0'
    
    def find_amenities(
        self,
        lat: float,
        lon: float,
        radius_m: int = 1000,
        amenity_types: Optional[List[str]] = None
    ) -> Dict[str, List[AmenityPoint]]:
        """
        Find amenities within radius of coordinates
        
        Args:
            lat: Latitude
            lon: Longitude
            radius_m: Search radius in meters (default 1km)
            amenity_types: List of amenity types to search for
                          (default: all available)
        
        Returns:
            Dict mapping amenity type -> list of AmenityPoint objects
        """
        if amenity_types is None:
            amenity_types = list(self.AMENITY_TYPES.keys())
        
        results: Dict[str, List[AmenityPoint]] = {t: [] for t in amenity_types}
        
        for amenity_type in amenity_types:
            if amenity_type not in self.AMENITY_TYPES:
                logger.warning(f"Unknown amenity type: {amenity_type}")
                continue
            
            tag_filter = self.AMENITY_TYPES[amenity_type]
            points = self._query_amenity_type(lat, lon, radius_m, tag_filter)
            results[amenity_type] = points
            
            # Rate limiting: Overpass API is free but ask for reasonable delays
            time.sleep(1)
        
        return results
    
    def _query_amenity_type(
        self,
        lat: float,
        lon: float,
        radius_m: int,
        tag_filter: str
    ) -> List[AmenityPoint]:
        """Query Overpass API for a single amenity type"""
        try:
            # Convert radius_m to decimal degrees (rough approximation)
            # 1 degree ≈ 111km at equator
            radius_deg = radius_m / 111000
            
            # Overpass QL query: find nodes/ways with tag filter within bbox
            query = f"""
            [bbox:{lat - radius_deg},{lon - radius_deg},{lat + radius_deg},{lon + radius_deg}];
            (
              node[{tag_filter}];
              way[{tag_filter}];
            );
            out center;
            """
            
            response = self.session.post(
                self.BASE_URL,
                data=query,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            points = []
            
            for element in data.get('elements', []):
                if 'center' in element:
                    # Way with center
                    p = element['center']
                elif 'lat' in element and 'lon' in element:
                    # Node
                    p = element
                else:
                    continue
                
                point = AmenityPoint(
                    amenity_type=tag_filter,
                    name=element.get('tags', {}).get('name'),
                    lat=p['lat'],
                    lon=p['lon'],
                    distance_m=self._haversine(lat, lon, p['lat'], p['lon'])
                )
                points.append(point)
            
            logger.info(f"Found {len(points)} points for {tag_filter}")
            return points
            
        except Exception as e:
            logger.error(f"Overpass query failed for {tag_filter}: {e}")
            return []
    
    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate great-circle distance between two points (meters)"""
        from math import radians, cos, sin, asin, sqrt
        
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371000  # Radius of earth in meters
        return c * r


class OpenRouteServiceRouter:
    """Calculate walking distances via Open Route Service"""
    
    BASE_URL = "https://api.openrouteservice.org/v2/matrix/foot"
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'house-research-amenity-scorer/1.0'
    
    def calculate_walking_distances(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_points: List[Tuple[float, float]]
    ) -> Dict[Tuple[float, float], Tuple[float, int]]:
        """
        Calculate walking distances/times from origin to destinations
        
        Args:
            origin_lat, origin_lon: Starting point
            destination_points: List of (lat, lon) tuples
        
        Returns:
            Dict mapping (lat, lon) -> (distance_m, time_s)
        """
        if not destination_points:
            return {}
        
        results: Dict[Tuple[float, float], Tuple[float, int]] = {}
        
        # Batch requests (ORS matrix API accepts up to 50 locations)
        batch_size = 49  # origin + 49 destinations
        
        for i in range(0, len(destination_points), batch_size):
            batch = destination_points[i:i+batch_size]
            batch_results = self._query_batch(origin_lat, origin_lon, batch)
            results.update(batch_results)
        
        return results
    
    def _query_batch(
        self,
        origin_lat: float,
        origin_lon: float,
        destinations: List[Tuple[float, float]]
    ) -> Dict[Tuple[float, float], Tuple[float, int]]:
        """Query ORS for a batch of destinations"""
        try:
            # Build request
            locations = [[origin_lon, origin_lat]] + [[lon, lat] for lat, lon in destinations]
            
            payload = {
                'locations': locations,
                'metrics': ['distance', 'duration'],
                'units': 'm'
            }
            
            response = self.session.post(
                self.BASE_URL,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            results: Dict[Tuple[float, float], Tuple[float, int]] = {}
            
            # First row contains distances/times from origin to all destinations
            if 'distances' in data and 'durations' in data:
                distances = data['distances'][0][1:]  # Skip origin itself
                durations = data['durations'][0][1:]
                
                for (lat, lon), dist, duration in zip(destinations, distances, durations):
                    results[(lat, lon)] = (dist, int(duration))
            
            return results
            
        except Exception as e:
            logger.error(f"ORS routing failed: {e}")
            return {}


class AmenityScorer:
    """Main amenity scoring orchestrator"""
    
    def __init__(self):
        self.geocoder = NominatimGeocoder()
        self.finder = OverpassAmenityFinder()
        self.router = OpenRouteServiceRouter()
    
    def score_address(
        self,
        address: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius_m: int = 1000
    ) -> Optional[AmenitySummary]:
        """
        Score amenities for an address
        
        Args:
            address: Property address
            lat, lon: Optional coordinates (will geocode if not provided)
            radius_m: Search radius in meters
        
        Returns:
            AmenitySummary with detailed amenity data and scoring
        """
        
        # Geocode if needed
        if lat is None or lon is None:
            logger.info(f"Geocoding address: {address}")
            result = self.geocoder.geocode(address)
            if not result:
                logger.error(f"Failed to geocode address: {address}")
                return None
            lat, lon = result
            logger.info(f"Geocoded to: {lat}, {lon}")
        
        # Find nearby amenities
        logger.info(f"Searching for amenities within {radius_m}m")
        amenities_by_type = self.finder.find_amenities(lat, lon, radius_m)
        
        # Collect all unique points for distance calculation
        all_points: List[Tuple[AmenityPoint, float, float]] = []
        for amenity_type, points in amenities_by_type.items():
            for point in points:
                all_points.append((point, lat, lon))
        
        # Calculate walking distances
        if all_points:
            logger.info(f"Calculating walking distances for {len(all_points)} points")
            dest_coords = [(p[0].lat, p[0].lon) for p in all_points]
            walking_data = self.router.calculate_walking_distances(lat, lon, dest_coords)
            
            # Update points with walking data
            for point, _, _ in all_points:
                key = (point.lat, point.lon)
                if key in walking_data:
                    distance_m, time_s = walking_data[key]
                    point.walking_distance_m = distance_m
                    point.walking_time_s = time_s
        
        # Calculate scoring
        scoring = self._calculate_scoring(amenities_by_type)
        
        return AmenitySummary(
            address=address,
            lat=lat,
            lon=lon,
            timestamp=datetime.utcnow().isoformat(),
            amenities_by_type=amenities_by_type,
            scoring=scoring
        )
    
    def _calculate_scoring(self, amenities_by_type: Dict[str, List[AmenityPoint]]) -> Dict[str, Any]:
        """Calculate summary scores for amenities"""
        scoring = {}
        
        for amenity_type, points in amenities_by_type.items():
            if not points:
                scoring[amenity_type] = {
                    'count': 0,
                    'avg_distance_m': None,
                    'avg_walking_time_s': None,
                    'nearest_m': None,
                    'description': f"No {amenity_type} found"
                }
                continue
            
            distances = [p.walking_distance_m or p.distance_m 
                        for p in points if p.walking_distance_m or p.distance_m]
            times = [p.walking_time_s for p in points if p.walking_time_s]
            
            avg_distance = sum(distances) / len(distances) if distances else None
            avg_time = sum(times) / len(times) if times else None
            nearest = min(distances) if distances else None
            
            # Format description
            count_str = f"{len(points)} {amenity_type}"
            if nearest:
                min_time = int(nearest / 1.4)  # Rough estimate: 1.4 m/s walking speed
                desc = f"{count_str}, nearest {nearest:.0f}m ({min_time}min walk)"
            else:
                desc = f"{count_str} within 1km"
            
            scoring[amenity_type] = {
                'count': len(points),
                'avg_distance_m': round(avg_distance, 1) if avg_distance else None,
                'avg_walking_time_s': round(avg_time, 0) if avg_time else None,
                'nearest_m': round(nearest, 1) if nearest else None,
                'description': desc
            }
        
        return scoring
    
    def to_json(self, summary: AmenitySummary) -> str:
        """Serialize summary to JSON"""
        return json.dumps(summary.to_dict(), indent=2)


def main():
    """Example usage"""
    scorer = AmenityScorer()
    
    # Test with a real Ballarat address
    address = "Sturt Street, Ballarat VIC, Australia"
    
    print(f"\n{'='*70}")
    print(f"Amenity Scoring: {address}")
    print(f"{'='*70}\n")
    
    result = scorer.score_address(address)
    
    if result:
        # Print summary
        print(f"Location: {result.address}")
        print(f"Coordinates: {result.lat:.4f}, {result.lon:.4f}")
        print(f"Timestamp: {result.timestamp}\n")
        
        print("Amenity Summary:")
        print("-" * 70)
        for amenity_type, score_data in result.scoring.items():
            print(f"  {amenity_type.title():20} {score_data['description']}")
        
        print("\n" + "="*70)
        print("Full JSON Output:")
        print("="*70)
        print(scorer.to_json(result))
    else:
        print("Failed to score address")


if __name__ == "__main__":
    main()
