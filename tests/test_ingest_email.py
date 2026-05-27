"""
Unit tests for ingest_email module

Tests covering:
- Property ingestion with URL preservation
- Email content parsing for URL extraction
- Property deduplication
- File I/O operations
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from ingest_email import EmailPropertyIngestor


class TestEmailPropertyIngestor:
    """Test EmailPropertyIngestor class"""
    
    @pytest.fixture
    def properties_file(self):
        """Create a temporary properties file for testing"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            data = {
                "properties": [
                    {
                        "id": "existing_001",
                        "address": "Existing Street, Ballarat VIC",
                        "price_aud": 300000,
                        "bedrooms": 2,
                        "bathrooms": 1,
                        "url": "https://www.realestate.com.au/property-house-vic-3350-existing"
                    }
                ],
                "last_updated": None
            }
            json.dump(data, f)
            return f.name
        
        # Cleanup
        Path(properties_file).unlink()
    
    def test_load_properties(self, properties_file):
        """Test loading properties from JSON"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        assert ingestor.load_properties()
        assert len(ingestor.properties) == 1
        assert ingestor.properties['existing_001']['address'] == "Existing Street, Ballarat VIC"
    
    def test_extract_url_from_content(self, properties_file):
        """Test extracting realestate.com.au URL from email content"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        
        email_content = """
        Check out this great property!
        https://www.realestate.com.au/property-house-vic-3350-test123
        Beautiful location with great amenities.
        """
        
        url = ingestor.extract_url(email_content)
        
        assert url is not None
        assert "realestate.com.au" in url
        assert "test123" in url
    
    def test_extract_url_without_www(self, properties_file):
        """Test extracting URL without www prefix"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        
        email_content = "https://realestate.com.au/property-house-vic-3350-test456"
        
        url = ingestor.extract_url(email_content)
        
        assert url is not None
        assert "test456" in url
    
    def test_extract_url_returns_none_for_no_url(self, properties_file):
        """Test that None is returned when no URL is found"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        
        email_content = "No URLs in this email"
        
        url = ingestor.extract_url(email_content)
        
        assert url is None
    
    def test_ingest_property_with_url(self, properties_file):
        """Test ingesting a property with a URL"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        ingestor.load_properties()
        
        property_data = {
            "id": "new_001",
            "address": "New Street, Ballarat VIC",
            "price_aud": 450000,
            "bedrooms": 3,
            "bathrooms": 2,
            "url": "https://www.realestate.com.au/property-house-vic-3350-new001"
        }
        
        assert ingestor.ingest_property(property_data)
        assert "new_001" in ingestor.properties
        assert ingestor.properties["new_001"]["url"] == property_data["url"]
    
    def test_ingest_property_without_id(self, properties_file):
        """Test ingesting a property without ID (should generate one)"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        ingestor.load_properties()
        
        property_data = {
            "address": "Generated ID Street, Ballarat VIC",
            "price_aud": 380000,
            "bedrooms": 2,
            "bathrooms": 1,
            "url": "https://www.realestate.com.au/property-house-vic-3350-gen001"
        }
        
        assert ingestor.ingest_property(property_data)
        
        # Check that an ID was generated
        assert "id" in property_data
        assert property_data["id"] in ingestor.properties
    
    def test_preserve_url_on_update(self, properties_file):
        """Test that existing URL is preserved when updating a property"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        ingestor.load_properties()
        
        # Update existing property without providing new URL
        property_data = {
            "id": "existing_001",
            "address": "Existing Street, Ballarat VIC",
            "price_aud": 350000  # Updated price
        }
        
        assert ingestor.ingest_property(property_data)
        
        # URL should be preserved from original
        assert ingestor.properties["existing_001"]["url"] == "https://www.realestate.com.au/property-house-vic-3350-existing"
    
    def test_process_email_content_extracts_url(self, properties_file):
        """Test that email processing extracts and adds URL to property data"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        
        email_content = """
        New property listing:
        https://www.realestate.com.au/property-house-vic-3350-email001
        """
        
        property_data = {
            "id": "email_001",
            "address": "Email Property Street",
            "price_aud": 500000
        }
        
        result = ingestor.process_email_content(email_content, property_data)
        
        assert "url" in result
        assert "email001" in result["url"]
    
    def test_ingest_email_message(self, properties_file):
        """Test complete email ingestion pipeline"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        ingestor.load_properties()
        
        email_content = """
        Property Details:
        Address: Email Test Street
        Price: $425,000 AUD
        
        Listing: https://www.realestate.com.au/property-house-vic-3350-emailtest
        """
        
        property_data = {
            "id": "email_test",
            "address": "Email Test Street",
            "price_aud": 425000,
            "bedrooms": 3,
            "bathrooms": 1
        }
        
        assert ingestor.ingest_email_message(email_content, property_data)
        
        # Check that URL was extracted and preserved
        assert "email_test" in ingestor.properties
        assert "url" in ingestor.properties["email_test"]
    
    def test_save_properties(self, properties_file):
        """Test saving ingested properties back to JSON"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        ingestor.load_properties()
        
        # Ingest new property
        property_data = {
            "id": "saved_001",
            "address": "Saved Street, Ballarat VIC",
            "price_aud": 475000,
            "bedrooms": 3,
            "bathrooms": 2,
            "url": "https://www.realestate.com.au/property-house-vic-3350-saved001"
        }
        ingestor.ingest_property(property_data)
        
        # Save
        assert ingestor.save_properties()
        
        # Reload and verify
        with open(properties_file) as f:
            data = json.load(f)
        
        assert len(data['properties']) == 2
        assert data['last_updated'] is not None
        
        saved_property = next((p for p in data['properties'] if p['id'] == 'saved_001'), None)
        assert saved_property is not None
        assert saved_property['url'] == "https://www.realestate.com.au/property-house-vic-3350-saved001"
    
    def test_run_pipeline(self, properties_file):
        """Test complete ingestion pipeline with email content"""
        ingestor = EmailPropertyIngestor(Path(properties_file))
        
        email_content = """
        Check out this property!
        https://www.realestate.com.au/property-house-vic-3350-pipeline
        """
        
        property_data = {
            "id": "pipeline_001",
            "address": "Pipeline Street, Ballarat VIC",
            "price_aud": 495000,
            "bedrooms": 4,
            "bathrooms": 2
        }
        
        assert ingestor.run(property_data, email_content)
        
        # Verify saved to file
        with open(properties_file) as f:
            data = json.load(f)
        
        pipeline_property = next((p for p in data['properties'] if p['id'] == 'pipeline_001'), None)
        assert pipeline_property is not None
        assert pipeline_property['url'] == "https://www.realestate.com.au/property-house-vic-3350-pipeline"


class TestURLPreservation:
    """Test URL preservation during ingestion"""
    
    def test_url_preserved_through_workflow(self):
        """Test that URLs are preserved through complete workflow"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            data = {"properties": []}
            json.dump(data, f)
            properties_file = f.name
        
        try:
            ingestor = EmailPropertyIngestor(Path(properties_file))
            
            # Step 1: Extract URL from email
            email_content = "https://www.realestate.com.au/property-house-vic-3350-workflow"
            extracted_url = ingestor.extract_url(email_content)
            
            # Step 2: Create property with URL
            property_data = {
                "id": "workflow_001",
                "address": "Workflow Street",
                "url": extracted_url
            }
            
            # Step 3: Ingest
            assert ingestor.run(property_data, email_content)
            
            # Step 4: Verify URL in saved file
            with open(properties_file) as f:
                data = json.load(f)
            
            assert data['properties'][0]['url'] == extracted_url
        
        finally:
            Path(properties_file).unlink()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
