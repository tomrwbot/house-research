#!/usr/bin/env python3
"""
Daily Digest Pipeline for House Research

Generates a daily digest of properties with rich amenity scoring.

Features:
- Loads properties from properties.json
- Scores each property using amenity_scorer
- Caches amenity data to avoid re-querying
- Generates a formatted digest summary
- Runs unattended via cron at 6:30 AM AWST

Author: house-research
License: MIT
"""

import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import time

# Add scripts to path
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

from amenity_scorer import AmenityScorer, AmenitySummary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DigestGenerator:
    """Generate daily digest with amenity scoring"""
    
    def __init__(self, properties_file: Path, mock_mode: bool = False):
        """
        Initialize digest generator
        
        Args:
            properties_file: Path to properties.json
            mock_mode: Use mock amenity data (for testing)
        """
        self.properties_file = properties_file
        self.scorer = AmenityScorer(mock_mode=mock_mode)
        self.properties = {}
        self.digest_data = {}
        self.mock_mode = mock_mode
    
    def load_properties(self) -> bool:
        """
        Load properties from JSON file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.properties_file, 'r') as f:
                data = json.load(f)
            
            self.properties = {p['id']: p for p in data.get('properties', [])}
            self.digest_data = data
            
            logger.info(f"Loaded {len(self.properties)} properties")
            return True
        
        except Exception as e:
            logger.error(f"Failed to load properties: {e}")
            return False
    
    def save_properties(self) -> bool:
        """
        Save updated properties (with cached amenity data) back to JSON
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update properties in digest data
            self.digest_data['properties'] = list(self.properties.values())
            self.digest_data['last_digest'] = datetime.utcnow().isoformat()
            
            with open(self.properties_file, 'w') as f:
                json.dump(self.digest_data, f, indent=2)
            
            logger.info("Saved updated properties with cached amenity data")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save properties: {e}")
            return False
    
    def score_property(self, prop_id: str, prop: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Score amenities for a single property
        
        Uses cached amenity data if available (not older than 7 days).
        Otherwise queries APIs and caches the result.
        
        Args:
            prop_id: Property identifier
            prop: Property data dict
        
        Returns:
            Enhanced property dict with scoring, or None if failed
        """
        # Check if we have cached, fresh amenity data
        if prop.get('amenity_data'):
            amenity_timestamp = datetime.fromisoformat(
                prop['amenity_data'].get('timestamp', '')
            )
            age_hours = (datetime.utcnow() - amenity_timestamp).total_seconds() / 3600
            
            if age_hours < 7 * 24:  # Less than 7 days old
                logger.info(f"Using cached amenity data for {prop_id} ({age_hours:.1f}h old)")
                return self._enhance_property_with_scores(prop)
        
        # Need to fetch fresh amenity data
        logger.info(f"Scoring amenities for {prop_id}: {prop.get('address', 'unknown')}")
        
        address = prop.get('address')
        lat = prop.get('lat')
        lon = prop.get('lon')
        
        if not address:
            logger.warning(f"No address for property {prop_id}")
            return None
        
        try:
            # Score amenities
            result = self.scorer.score_address(
                address=address,
                lat=lat,
                lon=lon,
                radius_m=1000
            )
            
            if result:
                # Cache the full amenity data
                prop['amenity_data'] = result.to_dict()
                logger.info(f"Cached amenity data for {prop_id}")
                return self._enhance_property_with_scores(prop)
            else:
                logger.error(f"Failed to score amenities for {prop_id}")
                return None
        
        except Exception as e:
            logger.error(f"Error scoring {prop_id}: {e}")
            return None
    
    def _enhance_property_with_scores(self, prop: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add calculated scores to property based on amenity data
        
        Args:
            prop: Property dict with amenity_data
        
        Returns:
            Enhanced property dict with scoring
        """
        if not prop.get('amenity_data'):
            return prop
        
        amenity_data = prop['amenity_data']
        scoring = amenity_data.get('scoring', {})
        
        # Calculate weighted amenity score (0-100)
        weights = {
            'schools': 0.20,
            'libraries': 0.10,
            'parks': 0.15,
            'cafes': 0.10,
            'supermarkets': 0.15,
            'restaurants': 0.10,
            'pharmacies': 0.10,
            'doctors': 0.10
        }
        
        total_score = 0
        breakdown = {}
        
        for amenity_type, weight in weights.items():
            if amenity_type not in scoring:
                continue
            
            count = scoring[amenity_type].get('count', 0)
            
            # Scoring: 5+ nearby amenities = excellent (100 pts)
            amenity_score = min(count / 5.0, 1.0) * 100
            contribution = amenity_score * weight
            total_score += contribution
            
            breakdown[amenity_type] = {
                'count': count,
                'score': round(amenity_score, 1),
                'contribution': round(contribution, 1)
            }
        
        prop['amenity_score'] = round(total_score, 1)
        prop['amenity_breakdown'] = breakdown
        
        return prop
    
    def generate_digest(self) -> Optional[str]:
        """
        Generate formatted digest of all properties with amenity scoring
        
        Returns:
            Formatted digest text, or None if failed
        """
        if not self.load_properties():
            return None
        
        digest_lines = [
            "=" * 80,
            "HOUSE RESEARCH DAILY DIGEST",
            f"Generated: {datetime.utcnow().isoformat()}",
            "=" * 80,
            ""
        ]
        
        # Score all properties
        scored_properties = []
        for prop_id, prop in self.properties.items():
            result = self.score_property(prop_id, prop)
            if result:
                scored_properties.append((prop_id, result))
            
            # Rate limiting: avoid hammering free APIs
            if len(scored_properties) < len(self.properties):
                time.sleep(1)
        
        if not scored_properties:
            digest_lines.append("No properties could be scored.\n")
            return "\n".join(digest_lines)
        
        # Sort by amenity score descending
        scored_properties.sort(
            key=lambda x: x[1].get('amenity_score', 0),
            reverse=True
        )
        
        # Generate property summaries
        for i, (prop_id, prop) in enumerate(scored_properties, 1):
            address = prop.get('address', 'Unknown')
            price = prop.get('price_aud', 0)
            bedrooms = prop.get('bedrooms', '?')
            bathrooms = prop.get('bathrooms', '?')
            amenity_score = prop.get('amenity_score', 0)
            url = prop.get('url')
            
            # Format property title with optional URL link
            if url:
                property_title = f"[{i}] [{address}]({url})"
            else:
                property_title = f"[{i}] {address}"
            
            digest_lines.append(f"\n{property_title}")
            digest_lines.append(f"    {'─' * 76}")
            digest_lines.append(
                f"    Price: ${price:,} AUD | "
                f"{bedrooms}BR / {bathrooms}BA | "
                f"Amenity Score: {amenity_score:.1f}/100"
            )
            
            # Add amenity breakdown
            if prop.get('amenity_data'):
                amenity_data = prop['amenity_data']
                scoring = amenity_data.get('scoring', {})
                
                digest_lines.append("\n    Nearby Amenities:")
                
                # Show top amenities with counts
                amenity_summaries = []
                for amenity_type in ['schools', 'parks', 'cafes', 'libraries', 'supermarkets']:
                    if amenity_type in scoring:
                        count = scoring[amenity_type].get('count', 0)
                        desc = scoring[amenity_type].get('description', '')
                        if count > 0:
                            amenity_summaries.append(f"      • {desc}")
                
                if amenity_summaries:
                    digest_lines.extend(amenity_summaries)
                else:
                    digest_lines.append("      • No major amenities found within 1km")
            
            # Add property details
            land_area = prop.get('land_area_sqm', '?')
            year_built = prop.get('year_built', '?')
            digest_lines.append(f"\n    Details: {land_area}m² | Built {year_built}")
        
        # Summary statistics
        digest_lines.extend([
            "\n" + "=" * 80,
            "SUMMARY",
            "=" * 80
        ])
        
        avg_amenity_score = sum(
            p[1].get('amenity_score', 0) for p in scored_properties
        ) / len(scored_properties)
        
        digest_lines.append(f"Total Properties: {len(scored_properties)}")
        digest_lines.append(f"Average Amenity Score: {avg_amenity_score:.1f}/100")
        digest_lines.append("")
        
        return "\n".join(digest_lines)
    
    def run(self) -> bool:
        """
        Run the complete digest pipeline
        
        1. Load properties
        2. Score each with amenity data (use cache if available)
        3. Generate formatted digest
        4. Save updated properties (with cache)
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Starting daily digest pipeline")
        
        # Generate digest
        digest_text = self.generate_digest()
        if not digest_text:
            logger.error("Failed to generate digest")
            return False
        
        # Save updated properties with cached amenity data
        if not self.save_properties():
            logger.error("Failed to save properties")
            return False
        
        # Output digest
        print(digest_text)
        
        logger.info("Daily digest pipeline completed successfully")
        return True


def main():
    """Main entry point"""
    # Find properties.json (should be in repo root)
    repo_root = Path(__file__).parent.parent
    properties_file = repo_root / 'properties.json'
    
    if not properties_file.exists():
        logger.error(f"Properties file not found: {properties_file}")
        return False
    
    # Use mock mode if --mock flag is present
    import sys
    mock_mode = '--mock' in sys.argv
    
    generator = DigestGenerator(properties_file, mock_mode=mock_mode)
    return generator.run()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
