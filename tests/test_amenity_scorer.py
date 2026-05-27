"""
Unit tests for amenity_scorer module

Tests covering:
- Geocoding
- Overpass API queries
- ORS routing
- Data deduplication
- Scoring calculations
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from amenity_scorer import (
    AmenityPoint,
    AmenitySummary,
    NominatimGeocoder,
    OverpassAmenityFinder,
    OpenRouteServiceRouter,
    AmenityScorer
)


class TestAmenityPoint:
    """Test AmenityPoint data class"""
    
    def test_amenity_point_creation(self):
        point = AmenityPoint(
            amenity_type='school',
            name='Test School',
            lat=-37.5,
            lon=143.5,
            distance_m=500.0
        )
        assert point.amenity_type == 'school'
        assert point.name == 'Test School'
        assert point.lat == -37.5
        assert point.lon == 143.5
        assert point.distance_m == 500.0
    
    def test_amenity_point_to_dict(self):
        point = AmenityPoint(
            amenity_type='cafe',
            name='Coffee Shop',
            lat=-37.5,
            lon=143.5,
            distance_m=250.0,
            walking_distance_m=300.0,
            walking_time_s=216
        )
        data = point.to_dict()
        assert isinstance(data, dict)
        assert data['amenity_type'] == 'cafe'
        assert data['walking_time_s'] == 216


class TestNominatimGeocoder:
    """Test Nominatim geocoding"""
    
    @patch('requests.Session.get')
    def test_geocode_success(self, mock_get):
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                'lat': '-37.5612',
                'lon': '143.8503'
            }
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        geocoder = NominatimGeocoder()
        result = geocoder.geocode("Sturt Street, Ballarat VIC")
        
        assert result is not None
        lat, lon = result
        assert abs(lat - (-37.5612)) < 0.0001
        assert abs(lon - 143.8503) < 0.0001
    
    @patch('requests.Session.get')
    def test_geocode_not_found(self, mock_get):
        # Mock empty response
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        geocoder = NominatimGeocoder()
        result = geocoder.geocode("Nonexistent Place XYZ")
        
        assert result is None
    
    @patch('requests.Session.get')
    def test_geocode_network_error(self, mock_get):
        mock_get.side_effect = Exception("Network error")
        
        geocoder = NominatimGeocoder()
        result = geocoder.geocode("Some Address")
        
        assert result is None


class TestOverpassAmenityFinder:
    """Test Overpass API amenity discovery"""
    
    def test_amenity_types_defined(self):
        finder = OverpassAmenityFinder()
        assert 'schools' in finder.AMENITY_TYPES
        assert 'libraries' in finder.AMENITY_TYPES
        assert 'parks' in finder.AMENITY_TYPES
        assert 'cafes' in finder.AMENITY_TYPES
        assert 'supermarkets' in finder.AMENITY_TYPES
    
    def test_haversine_distance(self):
        finder = OverpassAmenityFinder()
        
        # Ballarat to itself should be ~0
        dist = finder._haversine(-37.5612, 143.8503, -37.5612, 143.8503)
        assert dist < 10  # Less than 10 meters
        
        # Rough test: distance should increase with lat/lon difference
        dist1 = finder._haversine(-37.5612, 143.8503, -37.5612, 143.9503)
        dist2 = finder._haversine(-37.5612, 143.8503, -37.4612, 143.8503)
        assert dist1 > 0
        assert dist2 > 0
    
    @patch('requests.Session.post')
    def test_query_amenity_type_success(self, mock_post):
        # Mock Overpass response
        mock_response = Mock()
        mock_response.json.return_value = {
            'elements': [
                {
                    'type': 'node',
                    'id': 1,
                    'lat': -37.5600,
                    'lon': 143.8500,
                    'tags': {'name': 'Test School'}
                },
                {
                    'type': 'way',
                    'id': 2,
                    'center': {'lat': -37.5620, 'lon': 143.8520},
                    'tags': {'name': 'Another School'}
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        finder = OverpassAmenityFinder()
        points = finder._query_amenity_type(-37.5612, 143.8503, 1000, 'amenity=school')
        
        assert len(points) == 2
        assert points[0].name == 'Test School'
        assert points[1].name == 'Another School'
        assert all(p.amenity_type == 'amenity=school' for p in points)
        assert all(p.distance_m is not None for p in points)
    
    @patch('requests.Session.post')
    def test_query_amenity_type_empty(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {'elements': []}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        finder = OverpassAmenityFinder()
        points = finder._query_amenity_type(-37.5612, 143.8503, 1000, 'amenity=school')
        
        assert len(points) == 0


class TestOpenRouteServiceRouter:
    """Test ORS routing"""
    
    @patch('requests.Session.post')
    def test_calculate_walking_distances_success(self, mock_post):
        # Mock ORS response
        mock_response = Mock()
        mock_response.json.return_value = {
            'distances': [
                [0, 500, 750, 1200]  # distances from origin to 3 destinations
            ],
            'durations': [
                [0, 360, 540, 864]  # times in seconds
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        router = OpenRouteServiceRouter()
        destinations = [(-37.5600, 143.8500), (-37.5700, 143.8600), (-37.5500, 143.8400)]
        
        result = router.calculate_walking_distances(-37.5612, 143.8503, destinations)
        
        assert len(result) == 3
        assert result[(-37.5600, 143.8500)] == (500, 360)
        assert result[(-37.5700, 143.8600)] == (750, 540)
        assert result[(-37.5500, 143.8400)] == (1200, 864)
    
    @patch('requests.Session.post')
    def test_calculate_walking_distances_empty(self, mock_post):
        router = OpenRouteServiceRouter()
        result = router.calculate_walking_distances(-37.5612, 143.8503, [])
        
        assert result == {}
    
    @patch('requests.Session.post')
    def test_calculate_walking_distances_network_error(self, mock_post):
        mock_post.side_effect = Exception("Network error")
        
        router = OpenRouteServiceRouter()
        result = router.calculate_walking_distances(-37.5612, 143.8503, [(-37.5600, 143.8500)])
        
        assert result == {}


class TestAmenityScorer:
    """Test main scoring orchestrator"""
    
    @patch.object(NominatimGeocoder, 'geocode')
    @patch.object(OverpassAmenityFinder, 'find_amenities')
    @patch.object(OpenRouteServiceRouter, 'calculate_walking_distances')
    def test_score_address_with_geocoding(self, mock_router, mock_finder, mock_geocoder):
        # Setup mocks
        mock_geocoder.return_value = (-37.5612, 143.8503)
        
        mock_finder.return_value = {
            'schools': [
                AmenityPoint('school', 'School A', -37.5600, 143.8500, distance_m=200)
            ],
            'libraries': [
                AmenityPoint('library', 'Library B', -37.5620, 143.8520, distance_m=300)
            ],
            'parks': [],
            'cafes': [],
            'supermarkets': [],
            'restaurants': [],
            'pharmacies': [],
            'doctors': []
        }
        
        mock_router.return_value = {
            (-37.5600, 143.8500): (250, 180),
            (-37.5620, 143.8520): (350, 252)
        }
        
        scorer = AmenityScorer()
        result = scorer.score_address("Sturt Street, Ballarat")
        
        assert result is not None
        assert result.address == "Sturt Street, Ballarat"
        assert abs(result.lat - (-37.5612)) < 0.0001
        assert abs(result.lon - 143.8503) < 0.0001
        assert 'schools' in result.scoring
        assert 'libraries' in result.scoring
    
    @patch.object(NominatimGeocoder, 'geocode')
    def test_score_address_with_coordinates(self, mock_geocoder):
        mock_geocoder.return_value = None  # Should not be called
        
        with patch.object(OverpassAmenityFinder, 'find_amenities') as mock_finder, \
             patch.object(OpenRouteServiceRouter, 'calculate_walking_distances') as mock_router:
            
            mock_finder.return_value = {
                'schools': [],
                'libraries': [],
                'parks': [],
                'cafes': [],
                'supermarkets': [],
                'restaurants': [],
                'pharmacies': [],
                'doctors': []
            }
            mock_router.return_value = {}
            
            scorer = AmenityScorer()
            result = scorer.score_address("Address", lat=-37.5612, lon=143.8503)
            
            # Geocoder should not be called
            mock_geocoder.assert_not_called()
            assert result is not None
    
    def test_calculate_scoring(self):
        scorer = AmenityScorer()
        
        amenities_by_type = {
            'schools': [
                AmenityPoint('school', 'School A', -37.5600, 143.8500, 
                           walking_distance_m=250, walking_time_s=180),
                AmenityPoint('school', 'School B', -37.5620, 143.8520,
                           walking_distance_m=400, walking_time_s=288)
            ],
            'libraries': [],
            'parks': [
                AmenityPoint('park', 'Park C', -37.5580, 143.8480,
                           walking_distance_m=500, walking_time_s=360)
            ]
        }
        
        scoring = scorer._calculate_scoring(amenities_by_type)
        
        # Schools: 2 found, avg distance 325m
        assert scoring['schools']['count'] == 2
        assert scoring['schools']['avg_distance_m'] == 325.0
        assert scoring['schools']['nearest_m'] == 250.0
        
        # Libraries: none found
        assert scoring['libraries']['count'] == 0
        assert scoring['libraries']['avg_distance_m'] is None
        
        # Parks: 1 found
        assert scoring['parks']['count'] == 1
        assert scoring['parks']['nearest_m'] == 500.0
    
    def test_to_json(self):
        scorer = AmenityScorer()
        
        summary = AmenitySummary(
            address="Test Address",
            lat=-37.5612,
            lon=143.8503,
            timestamp=datetime.utcnow().isoformat(),
            amenities_by_type={
                'schools': [
                    AmenityPoint('school', 'School A', -37.5600, 143.8500, distance_m=200)
                ]
            },
            scoring={'schools': {'count': 1, 'description': 'Test'}}
        )
        
        json_str = scorer.to_json(summary)
        data = json.loads(json_str)
        
        assert data['address'] == "Test Address"
        assert data['lat'] == -37.5612
        assert 'schools' in data['amenities_by_type']
        assert len(data['amenities_by_type']['schools']) == 1


class TestIntegration:
    """Integration tests with minimal mocking"""
    
    @patch('requests.Session.get')
    @patch('requests.Session.post')
    def test_end_to_end_scoring(self, mock_post, mock_get):
        # Mock Nominatim
        nom_response = Mock()
        nom_response.json.return_value = [{'lat': '-37.5612', 'lon': '143.8503'}]
        nom_response.raise_for_status = Mock()
        
        # Mock Overpass (2 calls: schools, libraries)
        overpass_response = Mock()
        overpass_response.json.return_value = {
            'elements': [
                {'type': 'node', 'id': 1, 'lat': -37.5600, 'lon': 143.8500,
                 'tags': {'name': 'School A'}}
            ]
        }
        overpass_response.raise_for_status = Mock()
        
        # Mock ORS
        ors_response = Mock()
        ors_response.json.return_value = {
            'distances': [[0, 250]],
            'durations': [[0, 180]]
        }
        ors_response.raise_for_status = Mock()
        
        # Setup side_effect to return different responses
        def side_effect_get(*args, **kwargs):
            return nom_response
        
        def side_effect_post(*args, **kwargs):
            # First call is Overpass, return 8 times (for 8 amenity types)
            if 'overpass' in str(args[0]):
                return overpass_response
            else:
                return ors_response
        
        mock_get.side_effect = side_effect_get
        
        with patch('time.sleep'):  # Skip rate limit delays
            mock_post.side_effect = side_effect_post
            
            scorer = AmenityScorer()
            result = scorer.score_address("Test Address")
        
        assert result is not None
        assert 'schools' in result.scoring or 'schools' in result.amenities_by_type


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
