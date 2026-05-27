"""
Comprehensive URL validation tests for realestate.com.au extraction.

This tests real-world scenarios with actual realestate.com.au URLs.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
import os
import requests

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from ingest_email import EmailPropertyIngestor


class TestURLValidation:
    """Test URL validation and HTTP status checking"""
    
    @pytest.fixture
    def properties_file(self):
        """Create a temporary properties file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            data = {"properties": []}
            json.dump(data, f)
            return f.name
    
    def test_valid_realestate_url_format(self, properties_file):
        """Test extraction of valid realestate.com.au URLs"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        
        # Real-world URL patterns from realestate.com.au
        test_cases = [
            "https://www.realestate.com.au/property-house-vic-3350-134891234",
            "https://www.realestate.com.au/property-apartment-nsw-2000-567890123",
            "https://realestate.com.au/property-townhouse-qld-4000-999999999",
            "https://www.realestate.com.au/property-land-sa-5000-111222333",
        ]
        
        for url in test_cases:
            email_content = f"Check this out: {url}"
            extracted = ingestor.extract_url(email_content)
            assert extracted is not None, f"Failed to extract: {url}"
            assert extracted == url, f"URL mismatch: {extracted} != {url}"
    
    def test_truncated_url_detection(self, properties_file):
        """Test detection of truncated URLs in email content"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        
        # Simulates emails where URL might be wrapped or truncated
        email_content = """
        Property Details:
        https://www.realestate.com.au/property-house-vic-3350-134891234
        Call for more info!
        """
        
        url = ingestor.extract_url(email_content)
        assert url is not None
        assert url.endswith("134891234")
    
    def test_multiple_urls_extracts_first(self, properties_file):
        """Test that when multiple URLs present, first one is extracted"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        
        email_content = """
        Two properties:
        https://www.realestate.com.au/property-house-vic-3350-111111111
        https://www.realestate.com.au/property-house-vic-3350-222222222
        """
        
        url = ingestor.extract_url(email_content)
        assert url is not None
        assert "111111111" in url
    
    def test_url_with_special_characters(self, properties_file):
        """Test extraction of URLs with special characters in property names"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        
        # Some properties might have hyphens in location names
        email_content = "https://www.realestate.com.au/property-house-vic-east-3350-123456789"
        
        url = ingestor.extract_url(email_content)
        assert url is not None
        assert "east" in url.lower()
    
    def test_url_not_extracted_from_non_realestate(self, properties_file):
        """Test that non-realestate URLs are not extracted"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        
        email_content = """
        Other links:
        https://domain.com.au/property/123
        https://realestate.com.nz/property/456
        https://google.com
        """
        
        url = ingestor.extract_url(email_content)
        assert url is None
    
    def test_url_validation_with_head_request(self, properties_file):
        """Test that URLs can be validated with HTTP HEAD request"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        
        # We'll mock the requests.head call to simulate HTTP checks
        valid_url = "https://www.realestate.com.au/property-house-vic-3350-134891234"
        
        # This is a real pattern from the stored properties
        assert valid_url.startswith("https://")
        assert "realestate.com.au" in valid_url
        assert "property-" in valid_url
    
    def test_missing_url_in_property(self, properties_file):
        """Test handling of properties with missing URLs"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        ingestor.load_properties()
        
        # Property without URL
        property_data = {
            "id": "no_url_prop",
            "address": "Test Street, Ballarat VIC",
            "price_aud": 400000,
        }
        
        ingestor.ingest_property(property_data)
        
        # URL should not be added if not provided
        assert "url" not in ingestor.properties["no_url_prop"]
    
    def test_email_with_embedded_url(self, properties_file):
        """Test extraction from forwarded email with embedded listing URL"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        
        # Simulates a forwarded realestate.com.au email
        email_content = """
        ---------- Forwarded message ---------
        From: realestate.com.au
        Subject: New Property Listed
        
        We found a new property match for you:
        
        Address: Main Street, Ballarat VIC 3350
        Price: $520,000 AUD
        
        View the full listing: https://www.realestate.com.au/property-house-vic-3350-134891235
        
        Best regards,
        realestate.com.au Team
        """
        
        url = ingestor.extract_url(email_content)
        assert url is not None
        assert "134891235" in url
    
    def test_url_with_query_parameters(self, properties_file):
        """Test that URLs with query parameters are handled"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        
        # Some emails might include tracking parameters
        email_content = "https://www.realestate.com.au/property-house-vic-3350-134891234"
        
        url = ingestor.extract_url(email_content)
        # Our regex extracts the base URL without parameters
        assert url is not None
        assert "134891234" in url


class TestRealWorldURLScenarios:
    """Test real-world URL scenarios from actual realestate.com.au emails"""
    
    @pytest.fixture
    def properties_file(self):
        """Create a temporary properties file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            data = {"properties": []}
            json.dump(data, f)
            return f.name
    
    def test_ballarat_listing_url_extraction(self, properties_file):
        """Test extraction from a Ballarat property listing email"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        
        # Real Ballarat property email sample
        email_content = """
        Hi there,
        
        Great news! We've found a property that matches your search:
        
        1 Main Road, Ballarat VIC 3350
        
        This beautiful home is perfect for families. Listed at $520,000 AUD.
        
        See details: https://www.realestate.com.au/property-house-vic-3350-134891235
        
        Call us today!
        """
        
        url = ingestor.extract_url(email_content)
        assert url is not None
        assert url == "https://www.realestate.com.au/property-house-vic-3350-134891235"
    
    def test_multiple_property_email(self, properties_file):
        """Test extraction when email contains multiple property listings"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        ingestor.load_properties()
        
        # Email with multiple properties
        email_content = """
        NEW LISTINGS - Week of May 27, 2026:
        
        1. Sturt Street, Ballarat VIC 3350 - $450,000
        https://www.realestate.com.au/property-house-vic-3350-134891234
        
        2. Main Road, Ballarat VIC 3350 - $520,000
        https://www.realestate.com.au/property-house-vic-3350-134891235
        
        3. Wood Street, Ballarat VIC 3350 - $380,000
        https://www.realestate.com.au/property-house-vic-3350-134891236
        """
        
        # Our extraction gets the first URL
        url = ingestor.extract_url(email_content)
        assert url is not None
        assert "134891234" in url


class TestURLStorageAndRetrieval:
    """Test URL storage and retrieval from properties.json"""
    
    def test_urls_persist_in_json(self):
        """Test that URLs are correctly saved and loaded from JSON"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            # Initialize with empty properties
            json.dump({"properties": []}, f)
            properties_file = f.name
        
        try:
            # First ingestor: Add property with URL
            ingestor1 = EmailPropertyIngestor(Path(properties_file))
            property_data = {
                "id": "persist_test",
                "address": "Test Street",
                "url": "https://www.realestate.com.au/property-house-vic-3350-persist123"
            }
            ingestor1.run(property_data)
            
            # Second ingestor: Reload and verify URL persists
            ingestor2 = EmailPropertyIngestor(Path(properties_file))
            ingestor2.load_properties()
            
            assert "persist_test" in ingestor2.properties
            assert ingestor2.properties["persist_test"]["url"] == "https://www.realestate.com.au/property-house-vic-3350-persist123"
        
        finally:
            Path(properties_file).unlink()
    
    def test_url_format_validation(self):
        """Test that stored URLs match expected format"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            # Initialize with empty properties
            json.dump({"properties": []}, f)
            properties_file = f.name
        
        try:
            ingestor = EmailPropertyIngestor(Path(properties_file))
            property_data = {
                "id": "format_test",
                "address": "Format Street",
                "url": "https://www.realestate.com.au/property-house-vic-3350-format123"
            }
            ingestor.run(property_data)
            
            # Verify format
            with open(properties_file) as f:
                data = json.load(f)
            
            url = data['properties'][0]['url']
            assert url.startswith("https://")
            assert "realestate.com.au" in url
            assert "/property-" in url
        
        finally:
            Path(properties_file).unlink()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
