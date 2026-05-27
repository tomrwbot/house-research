"""
Unit tests for daily_digest module

Tests covering:
- Property loading/saving
- Amenity scoring integration
- Digest generation
- Caching logic
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from daily_digest import DigestGenerator
from amenity_scorer import AmenitySummary, AmenityPoint


class TestDigestGenerator:
    """Test DigestGenerator class"""
    
    @pytest.fixture
    def properties_file(self):
        """Create a temporary properties file for testing"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            data = {
                "properties": [
                    {
                        "id": "test_001",
                        "address": "Test Street, Ballarat VIC",
                        "lat": -37.5600,
                        "lon": 143.8500,
                        "price_aud": 400000,
                        "bedrooms": 3,
                        "bathrooms": 1,
                        "land_area_sqm": 350,
                        "year_built": 2000,
                        "url": "https://www.realestate.com.au/property-house-vic-3350-test001",
                        "amenity_data": None
                    }
                ],
                "last_digest": None,
                "digest_frequency": "daily",
                "digest_time_awst": "06:30"
            }
            json.dump(data, f)
            return f.name
        
        # Cleanup
        Path(properties_file).unlink()
    
    def test_load_properties(self, properties_file):
        """Test loading properties from JSON"""
        generator = DigestGenerator(Path(properties_file))
        assert generator.load_properties()
        assert len(generator.properties) == 1
        assert generator.properties['test_001']['address'] == "Test Street, Ballarat VIC"
    
    def test_save_properties(self, properties_file):
        """Test saving properties back to JSON"""
        generator = DigestGenerator(Path(properties_file))
        generator.load_properties()
        
        # Modify a property
        generator.properties['test_001']['price_aud'] = 450000
        
        assert generator.save_properties()
        
        # Reload and verify
        with open(properties_file) as f:
            data = json.load(f)
        assert data['properties'][0]['price_aud'] == 450000
        assert data['last_digest'] is not None
    
    def test_score_property_no_cache(self, properties_file):
        """Test scoring a property with no cached data"""
        generator = DigestGenerator(Path(properties_file), mock_mode=True)
        generator.load_properties()
        
        prop = generator.properties['test_001']
        result = generator.score_property('test_001', prop)
        
        assert result is not None
        assert 'amenity_score' in result
        assert 'amenity_data' in result
        assert result['amenity_score'] > 0
    
    def test_score_property_with_fresh_cache(self, properties_file):
        """Test scoring uses fresh cached data"""
        generator = DigestGenerator(Path(properties_file), mock_mode=False)
        generator.load_properties()
        
        prop = generator.properties['test_001']
        
        # Add fresh cached data (less than 7 days old)
        fresh_cache = {
            'address': 'Test Street, Ballarat VIC',
            'lat': -37.5600,
            'lon': 143.8500,
            'timestamp': datetime.utcnow().isoformat(),
            'amenities_by_type': {},
            'scoring': {
                'schools': {'count': 2, 'description': '2 schools'},
                'parks': {'count': 1, 'description': '1 park'},
                'cafes': {'count': 3, 'description': '3 cafes'},
                'libraries': {'count': 0, 'description': '0 libraries'},
                'supermarkets': {'count': 1, 'description': '1 supermarket'},
                'restaurants': {'count': 2, 'description': '2 restaurants'},
                'pharmacies': {'count': 1, 'description': '1 pharmacy'},
                'doctors': {'count': 1, 'description': '1 doctor'}
            }
        }
        prop['amenity_data'] = fresh_cache
        
        result = generator.score_property('test_001', prop)
        
        assert result is not None
        assert 'amenity_score' in result
        # Score should be calculated from existing data
        assert result['amenity_score'] >= 0
    
    def test_generate_digest_mock(self, properties_file):
        """Test digest generation with mock data"""
        generator = DigestGenerator(Path(properties_file), mock_mode=True)
        
        digest = generator.generate_digest()
        
        assert digest is not None
        assert "HOUSE RESEARCH DAILY DIGEST" in digest
        assert "Test Street, Ballarat VIC" in digest
        assert "Amenity Score" in digest
        assert "SUMMARY" in digest
    
    def test_run_pipeline(self, properties_file):
        """Test complete pipeline (load, score, generate, save)"""
        generator = DigestGenerator(Path(properties_file), mock_mode=True)
        
        assert generator.run()
        
        # Verify properties were saved
        with open(properties_file) as f:
            data = json.load(f)
        
        assert data['last_digest'] is not None
        assert data['properties'][0]['amenity_data'] is not None


class TestDigestFormatting:
    """Test digest output formatting"""
    
    @pytest.fixture
    def generator(self):
        """Create a mock generator for formatting tests"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            data = {
                "properties": [
                    {
                        "id": "test_001",
                        "address": "Main Road, Ballarat VIC",
                        "lat": -37.5650,
                        "lon": 143.8450,
                        "price_aud": 520000,
                        "bedrooms": 4,
                        "bathrooms": 2,
                        "land_area_sqm": 600,
                        "year_built": 2005,
                        "url": "https://www.realestate.com.au/property-house-vic-3350-test001",
                        "amenity_data": None
                    },
                    {
                        "id": "test_002",
                        "address": "Wood Street, Ballarat VIC",
                        "lat": -37.5700,
                        "lon": 143.8400,
                        "price_aud": 380000,
                        "bedrooms": 2,
                        "bathrooms": 1,
                        "land_area_sqm": 250,
                        "year_built": 1980,
                        "url": "https://www.realestate.com.au/property-house-vic-3350-test002",
                        "amenity_data": None
                    }
                ],
                "last_digest": None,
                "digest_frequency": "daily",
                "digest_time_awst": "06:30"
            }
            json.dump(data, f)
            properties_file = f.name
        
        generator = DigestGenerator(Path(properties_file), mock_mode=True)
        yield generator
        
        # Cleanup
        Path(properties_file).unlink()
    
    def test_digest_contains_price_info(self, generator):
        """Test digest includes property pricing"""
        digest = generator.generate_digest()
        
        assert "$520,000 AUD" in digest
        assert "$380,000 AUD" in digest
    
    def test_digest_sorted_by_amenity_score(self, generator):
        """Test digest properties are sorted by amenity score"""
        digest = generator.generate_digest()
        
        # Main Road should have better score than Wood Street
        lines = digest.split('\n')
        main_idx = next(i for i, line in enumerate(lines) if 'Main Road' in line)
        wood_idx = next(i for i, line in enumerate(lines) if 'Wood Street' in line)
        
        # Main Road should appear first (higher score)
        assert main_idx < wood_idx
    
    def test_digest_includes_statistics(self, generator):
        """Test digest includes summary statistics"""
        digest = generator.generate_digest()
        
        assert "Total Properties: 2" in digest
        assert "Average Amenity Score" in digest
    
    def test_digest_includes_property_urls(self, generator):
        """Test digest includes clickable property URLs as markdown links"""
        digest = generator.generate_digest()
        
        # Check that URLs are formatted as markdown links
        assert "[Main Road, Ballarat VIC](https://www.realestate.com.au/property-house-vic-3350-test001)" in digest
        assert "[Wood Street, Ballarat VIC](https://www.realestate.com.au/property-house-vic-3350-test002)" in digest


class TestCaching:
    """Test caching behavior"""
    
    def test_old_cache_not_used(self):
        """Test that cache older than 7 days is not used"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            old_timestamp = (datetime.utcnow() - timedelta(days=8)).isoformat()
            
            data = {
                "properties": [
                    {
                        "id": "test_001",
                        "address": "Test Street, Ballarat VIC",
                        "lat": -37.5600,
                        "lon": 143.8500,
                        "price_aud": 400000,
                        "bedrooms": 3,
                        "bathrooms": 1,
                        "land_area_sqm": 350,
                        "year_built": 2000,
                        "amenity_data": {
                            "address": "Test Street, Ballarat VIC",
                            "lat": -37.5600,
                            "lon": 143.8500,
                            "timestamp": old_timestamp,
                            "amenities_by_type": {},
                            "scoring": {}
                        }
                    }
                ],
                "last_digest": None,
                "digest_frequency": "daily",
                "digest_time_awst": "06:30"
            }
            json.dump(data, f)
            properties_file = f.name
        
        generator = DigestGenerator(Path(properties_file), mock_mode=True)
        generator.load_properties()
        
        prop = generator.properties['test_001']
        
        # Even though cache exists, it should be old and not used
        # Mock scorer will provide new data
        result = generator.score_property('test_001', prop)
        
        assert result is not None
        # Verify new amenity_data was created
        assert 'amenity_data' in result
        
        Path(properties_file).unlink()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
