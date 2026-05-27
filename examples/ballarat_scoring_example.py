#!/usr/bin/env python3
"""
Example: Property Amenity Scoring for Ballarat Addresses

This example demonstrates:
1. Basic amenity scoring for a single address
2. Integration with property valuation scoring
3. Batch processing multiple addresses
4. Handling rate limiting gracefully
"""

import sys
import json
import time
from pathlib import Path

# Add scripts to path
scripts_dir = Path(__file__).parent.parent / 'scripts'
sys.path.insert(0, str(scripts_dir))

from amenity_scorer import AmenityScorer


def score_single_property(address: str, radius_m: int = 1000) -> dict:
    """Score amenities for a single property address"""
    scorer = AmenityScorer()
    result = scorer.score_address(address, radius_m=radius_m)
    
    if not result:
        return {'status': 'error', 'address': address}
    
    return {
        'status': 'success',
        'address': result.address,
        'coordinates': {'lat': result.lat, 'lon': result.lon},
        'amenities': result.scoring,
        'raw_data': result.to_dict()
    }


def property_amenity_score(address: str, radius_m: int = 1000) -> dict:
    """
    Calculate a weighted amenity score for property valuation
    
    Returns a score 0–100 where:
    - 0   = No amenities nearby (poor location)
    - 50  = Average amenities (typical suburban)
    - 100 = Excellent amenities (urban/premium location)
    """
    scorer = AmenityScorer()
    result = scorer.score_address(address, radius_m=radius_m)
    
    if not result:
        return {
            'amenity_score': None,
            'status': 'error',
            'error': 'Could not score amenities'
        }
    
    # Weighted scoring (customize per region)
    weights = {
        'schools': 0.20,      # High priority for families
        'libraries': 0.10,
        'parks': 0.15,        # Recreation & greenspace
        'cafes': 0.10,
        'supermarkets': 0.15, # Essential services
        'restaurants': 0.10,
        'pharmacies': 0.10,
        'doctors': 0.10
    }
    
    total_score = 0
    breakdown = {}
    
    for amenity_type, weight in weights.items():
        count = result.scoring[amenity_type]['count']
        
        # Scoring: 5+ nearby amenities of this type = excellent (100 pts)
        # Scale: 0 amenities = 0 pts, 1 = 20 pts, 2 = 40 pts, etc.
        amenity_score = min(count / 5.0, 1.0) * 100
        contribution = amenity_score * weight
        total_score += contribution
        
        breakdown[amenity_type] = {
            'count': count,
            'score': round(amenity_score, 1),
            'contribution': round(contribution, 1),
            'weight': f'{weight:.0%}'
        }
    
    return {
        'status': 'success',
        'address': result.address,
        'amenity_score': round(total_score, 1),
        'breakdown': breakdown,
        'coordinates': {'lat': result.lat, 'lon': result.lon},
        'interpretation': interpret_score(total_score)
    }


def interpret_score(score: float) -> str:
    """Interpret amenity score for property valuation"""
    if score >= 80:
        return "Excellent — Premium location with abundant amenities"
    elif score >= 60:
        return "Good — Well-serviced area with most amenities nearby"
    elif score >= 40:
        return "Average — Standard suburban amenities"
    elif score >= 20:
        return "Below Average — Limited nearby amenities"
    else:
        return "Poor — Very few amenities within 1km"


def batch_score_addresses(addresses: list) -> list:
    """Score multiple addresses with rate limiting"""
    results = []
    
    for i, address in enumerate(addresses, 1):
        print(f"\n[{i}/{len(addresses)}] Scoring: {address}")
        
        try:
            result = property_amenity_score(address)
            results.append(result)
            
            if result['status'] == 'success':
                print(f"  Score: {result['amenity_score']}/100")
                print(f"  {result['interpretation']}")
            else:
                print(f"  ✗ Failed: {result['error']}")
            
            # Rate limiting: respect free API quotas
            if i < len(addresses):
                time.sleep(2)
        
        except Exception as e:
            print(f"  ✗ Error: {e}")
            results.append({'status': 'error', 'address': address, 'error': str(e)})
    
    return results


def main():
    """Example: Score several Ballarat properties"""
    
    print("="*70)
    print("BALLARAT PROPERTY AMENITY SCORING EXAMPLE")
    print("="*70)
    
    # Example 1: Single property with detailed output
    print("\n" + "="*70)
    print("EXAMPLE 1: Single Property Scoring")
    print("="*70)
    
    address = "Sturt Street, Ballarat VIC, Australia"
    result = property_amenity_score(address)
    
    if result['status'] == 'success':
        print(f"\nAddress: {result['address']}")
        print(f"Coordinates: {result['coordinates']['lat']:.4f}, {result['coordinates']['lon']:.4f}")
        print(f"\n✓ AMENITY SCORE: {result['amenity_score']}/100")
        print(f"  {result['interpretation']}\n")
        
        print("Breakdown by amenity type:")
        print("-" * 70)
        for amenity_type, data in result['breakdown'].items():
            print(f"  {amenity_type.title():20} {data['count']:2} found | "
                  f"Score: {data['score']:5.1f} | "
                  f"Contribution: {data['contribution']:5.1f}")
    else:
        print(f"\n✗ Failed to score: {result['error']}")
    
    # Example 2: Batch scoring (commented out to avoid long wait)
    print("\n" + "="*70)
    print("EXAMPLE 2: Batch Scoring (Demonstration)")
    print("="*70)
    print("\nBatch processing example (skipped to avoid API rate limiting):")
    print("""
    batch_addresses = [
        "Sturt Street, Ballarat VIC",
        "Main Road, Ballarat VIC",
        "Wood Street, Ballarat VIC"
    ]
    
    results = batch_score_addresses(batch_addresses)
    
    # Summary
    scores = [r['amenity_score'] for r in results if r['status'] == 'success']
    if scores:
        avg_score = sum(scores) / len(scores)
        print(f"\\nAverage amenity score: {avg_score:.1f}/100")
    """)
    
    # Example 3: Export to JSON
    print("\n" + "="*70)
    print("EXAMPLE 3: JSON Export")
    print("="*70)
    print("\nFull JSON output for integration with property database:")
    print(json.dumps(result, indent=2))
    
    # Example 4: House Research Integration
    print("\n" + "="*70)
    print("EXAMPLE 4: Integration with House Research Scoring")
    print("="*70)
    
    if result['status'] == 'success':
        # Example of combining with other scores
        mock_property_data = {
            'address': result['address'],
            'coordinates': result['coordinates'],
            'price': 450000,  # AUD
            'bedrooms': 3,
            'bathrooms': 1,
            'land_area_sqm': 350,
            'year_built': 1995,
            'amenity_score': result['amenity_score'],
            'amenity_breakdown': result['breakdown']
        }
        
        # Calculate composite score (example)
        composite = {
            'property_condition': 65,  # From other scoring
            'location_amenities': result['amenity_score'],
            'market_value': 72,  # From comparable sales
            'overall_rating': (65 + result['amenity_score'] + 72) / 3
        }
        
        print(f"\nSample House Research Output:")
        print(f"  Address: {mock_property_data['address']}")
        print(f"  Price: ${mock_property_data['price']:,}")
        print(f"  Bedrooms: {mock_property_data['bedrooms']}")
        print(f"  Amenity Score: {mock_property_data['amenity_score']}/100")
        print(f"  Overall Rating: {composite['overall_rating']:.1f}/100")
        
        print(f"\nFull composite scoring:")
        print(json.dumps(composite, indent=2))


if __name__ == "__main__":
    main()
