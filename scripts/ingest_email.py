#!/usr/bin/env python3
"""
Email Ingestion Pipeline for House Research

Ingests property data from email messages and preserves realestate.com.au URLs.

Features:
- Parses property information from email content
- Extracts and preserves realestate.com.au listing URLs
- Validates property data before adding to properties.json
- Deduplicates properties by ID or address
- Logs all ingestion activity

Author: house-research
License: MIT
"""

import json
import logging
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from email.mime.text import MIMEText
import email

# Add scripts to path
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EmailPropertyIngestor:
    """Ingest properties from email messages"""
    
    def __init__(self, properties_file: Path):
        """
        Initialize email ingestor
        
        Args:
            properties_file: Path to properties.json
        """
        self.properties_file = properties_file
        self.properties = {}
        self.digest_data = {}
        self.ingested_count = 0
    
    def load_properties(self) -> bool:
        """
        Load existing properties from JSON file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.properties_file, 'r') as f:
                data = json.load(f)
            
            self.properties = {p['id']: p for p in data.get('properties', [])}
            self.digest_data = data
            
            logger.info(f"Loaded {len(self.properties)} existing properties")
            return True
        
        except FileNotFoundError:
            logger.info("Properties file does not exist, will create new")
            self.digest_data = {'properties': []}
            return True
        except Exception as e:
            logger.error(f"Failed to load properties: {e}")
            return False
    
    def save_properties(self) -> bool:
        """
        Save updated properties back to JSON
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update properties in digest data
            self.digest_data['properties'] = list(self.properties.values())
            self.digest_data['last_updated'] = datetime.utcnow().isoformat()
            
            with open(self.properties_file, 'w') as f:
                json.dump(self.digest_data, f, indent=2)
            
            logger.info(f"Saved {len(self.properties)} properties")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save properties: {e}")
            return False
    
    def extract_url(self, content: str) -> Optional[str]:
        """
        Extract realestate.com.au URL from email content
        
        Args:
            content: Email text content
        
        Returns:
            realestate.com.au URL if found, None otherwise
        """
        # Match realestate.com.au URLs
        # Pattern: https://www.realestate.com.au/property-TYPE-LOCATION-ID
        pattern = r'https?://(?:www\.)?realestate\.com\.au/property-[a-z0-9\-]+'
        match = re.search(pattern, content, re.IGNORECASE)
        
        if match:
            url = match.group(0)
            logger.info(f"Extracted URL: {url}")
            return url
        
        return None
    
    def ingest_property(self, property_data: Dict[str, Any]) -> bool:
        """
        Ingest a single property, preserving URLs
        
        Args:
            property_data: Property data dict (must have 'id' or 'address')
        
        Returns:
            True if successfully ingested, False otherwise
        """
        # Validate required fields
        prop_id = property_data.get('id')
        address = property_data.get('address')
        
        if not prop_id and not address:
            logger.error("Property must have 'id' or 'address'")
            return False
        
        # Generate ID if not provided
        if not prop_id:
            # Create simple ID from address
            prop_id = address.replace(' ', '_').lower()[:50]
            property_data['id'] = prop_id
        
        # Check if property already exists
        if prop_id in self.properties:
            logger.warning(f"Property {prop_id} already exists, updating")
            
            # Preserve existing URL if not provided
            if 'url' not in property_data and 'url' in self.properties[prop_id]:
                property_data['url'] = self.properties[prop_id]['url']
        
        # Store property
        self.properties[prop_id] = property_data
        self.ingested_count += 1
        logger.info(f"Ingested property {prop_id}: {address}")
        
        return True
    
    def process_email_content(self, content: str, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process email content and extract/preserve URLs
        
        Args:
            content: Email message content
            property_data: Property data to enhance
        
        Returns:
            Enhanced property data with URL if found
        """
        # Extract URL from email content if not already present
        if 'url' not in property_data:
            url = self.extract_url(content)
            if url:
                property_data['url'] = url
        
        return property_data
    
    def ingest_email_message(self, email_content: str, property_data: Dict[str, Any]) -> bool:
        """
        Ingest property from email message
        
        Combines email processing with property ingestion.
        Ensures URLs are preserved throughout the process.
        
        Args:
            email_content: Raw email message content
            property_data: Property data dict (should have id, address, etc.)
        
        Returns:
            True if successfully ingested, False otherwise
        """
        # Process email to extract/preserve URLs
        enhanced_data = self.process_email_content(email_content, property_data)
        
        # Ingest the property
        return self.ingest_property(enhanced_data)
    
    def run(self, property_data: Dict[str, Any], email_content: str = "") -> bool:
        """
        Run the complete email ingestion pipeline
        
        1. Load existing properties
        2. Process email content (extract URLs)
        3. Ingest property with preserved URL
        4. Save updated properties
        
        Args:
            property_data: Property information dict
            email_content: Optional email message content
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Starting email ingestion pipeline")
        
        # Load existing properties
        if not self.load_properties():
            return False
        
        # Process and ingest
        if email_content:
            if not self.ingest_email_message(email_content, property_data):
                logger.error("Failed to ingest property from email")
                return False
        else:
            if not self.ingest_property(property_data):
                logger.error("Failed to ingest property")
                return False
        
        # Save updated properties
        if not self.save_properties():
            logger.error("Failed to save properties")
            return False
        
        logger.info(f"Email ingestion pipeline completed successfully ({self.ingested_count} properties ingested)")
        return True


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Ingest properties from email messages')
    parser.add_argument('--properties-file', type=Path, help='Path to properties.json')
    parser.add_argument('--id', type=str, help='Property ID')
    parser.add_argument('--address', type=str, help='Property address')
    parser.add_argument('--price', type=int, help='Property price in AUD')
    parser.add_argument('--bedrooms', type=int, help='Number of bedrooms')
    parser.add_argument('--bathrooms', type=int, help='Number of bathrooms')
    parser.add_argument('--url', type=str, help='Property listing URL')
    parser.add_argument('--email-content', type=str, help='Email content to parse')
    
    args = parser.parse_args()
    
    # Find properties.json if not specified
    properties_file = args.properties_file or Path(__file__).parent.parent / 'properties.json'
    
    if not properties_file.exists():
        logger.error(f"Properties file not found: {properties_file}")
        return False
    
    # Build property data
    property_data = {}
    if args.id:
        property_data['id'] = args.id
    if args.address:
        property_data['address'] = args.address
    if args.price:
        property_data['price_aud'] = args.price
    if args.bedrooms:
        property_data['bedrooms'] = args.bedrooms
    if args.bathrooms:
        property_data['bathrooms'] = args.bathrooms
    if args.url:
        property_data['url'] = args.url
    
    # Run ingestion
    ingestor = EmailPropertyIngestor(properties_file)
    return ingestor.run(property_data, args.email_content or "")


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
