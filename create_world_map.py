#!/usr/bin/env python3
"""
Create a simplified world map SVG from GeoJSON data.
Outputs a compact JSON file with country geometry for web display.
"""

import json
import sys

def simplify_geojson():
    """Load GeoJSON and create a simplified version for web use"""
    try:
        with open('world.geojson', 'r') as f:
            data = json.load(f)
        
        countries = {}
        
        for feature in data['features']:
            props = feature.get('properties', {})
            country_name = props.get('ADMIN') or props.get('name') or props.get('NAME')
            
            if not country_name:
                continue
            
            geom = feature.get('geometry', {})
            countries[country_name] = {
                'type': geom.get('type'),
                'coordinates': geom.get('coordinates')
            }
        
        print(f"Extracted {len(countries)} countries from GeoJSON")
        
        # Write simplified version
        with open('world-map-simplified.json', 'w') as f:
            json.dump(countries, f)
        
        print(f"Saved to world-map-simplified.json ({len(json.dumps(countries))} bytes)")
        
        # Also list country names for reference
        with open('world-map-countries.txt', 'w') as f:
            for name in sorted(countries.keys()):
                f.write(f"{name}\n")
        
        print(f"Country list: world-map-countries.txt")
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return True

if __name__ == '__main__':
    simplify_geojson()
