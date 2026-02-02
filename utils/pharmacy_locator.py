from typing import List, Dict, Optional
import requests
from utils.utils import setup_logger

logger = setup_logger(__name__)

class PharmacyLocator:
    def __init__(self):
        # OpenStreetMap Headers (Required by their Usage Policy)
        self.headers = {
            'User-Agent': 'pharmEZ-MedicalApp/1.0 (contact@example.com)'
        }
    
    def geocode_address(self, address: str) -> Optional[tuple]:
        """
        Geocode an address using OpenStreetMap Nominatim API
        Returns: (latitude, longitude) tuple or None
        """
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                "q": address,
                "format": "json",
                "limit": 1
            }
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            data = response.json()
            
            if data:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                logger.info(f"Geocoded '{address}': {lat}, {lon}")
                return (lat, lon)
            else:
                logger.warning("Geocoding failed: No results found.")
                return None
        except Exception as e:
            logger.error(f"Geocoding error: {str(e)}")
            return None # Frontend will handle this or default
    
    def find_nearby_pharmacies(
        self,
        latitude: float,
        longitude: float,
        radius: int = 5000,
        max_results: int = 15
    ) -> List[Dict]:
        """
        Find pharmacies using Overpass API (OpenStreetMap)
        """
        try:
            # Overpass QL query: Find nodes/ways with amenity=pharmacy within radius around lat,lon
            overpass_url = "https://overpass-api.de/api/interpreter"
            search_radius = radius  # meters
            
            # Query for pharmacies
            # [out:json];(node["amenity"="pharmacy"](around:radius,lat,lon);way["amenity"="pharmacy"](around:radius,lat,lon);relation["amenity"="pharmacy"](around:radius,lat,lon););out center;
            
            query = f"""
                [out:json];
                (
                  node["amenity"="pharmacy"](around:{search_radius},{latitude},{longitude});
                  way["amenity"="pharmacy"](around:{search_radius},{latitude},{longitude});
                  relation["amenity"="pharmacy"](around:{search_radius},{latitude},{longitude});
                );
                out center {max_results};
            """
            
            response = requests.post(overpass_url, data=query, timeout=25)
            data = response.json()
            
            pharmacies = []
            for element in data.get('elements', []):
                # Handle different element types (node vs way/relation have center)
                lat = element.get('lat') or element.get('center', {}).get('lat')
                lon = element.get('lon') or element.get('center', {}).get('lon')
                
                if not lat or not lon:
                    continue
                    
                tags = element.get('tags', {})
                name = tags.get('name', 'Unknown Pharmacy')
                
                # Format Address from available tags
                addr_parts = [
                    tags.get('addr:housenumber'),
                    tags.get('addr:street'),
                    tags.get('addr:city'),
                    tags.get('addr:postcode')
                ]
                address = ", ".join(filter(None, addr_parts))
                if not address:
                    address = "Address details not available"
                
                # Calculate distance
                dist = self.calculate_distance(latitude, longitude, lat, lon) * 1000 # to meters

                pharmacies.append({
                    "name": name,
                    "address": address,
                    "phone": tags.get('phone', tags.get('contact:phone', 'N/A')),
                    "latitude": lat,
                    "longitude": lon,
                    "distance": dist,
                    "rating": "N/A", # OSM doesn't have ratings
                    "is_open_now": tags.get('opening_hours', 'N/A'),
                    "source": "OpenStreetMap"
                })
            
            # Sort by distance
            pharmacies.sort(key=lambda x: x['distance'])
            
            # Fallback to sample data if empty (OSM might be sparse in some areas)
            if not pharmacies:
                logger.info("No OSM results found, returning sample data.")
                return self._get_sample_pharmacies_with_distance(latitude, longitude, radius)

            return pharmacies
            
        except Exception as e:
            logger.error(f"OSM Search Error: {e}")
            return self._get_sample_pharmacies_with_distance(latitude, longitude, radius)

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in km"""
        from math import radians, sin, cos, sqrt, atan2
        R = 6371
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c

    def _get_sample_pharmacies_with_distance(self, latitude: float, longitude: float, radius: int) -> List[Dict]:
        """Return sample pharmacies when API is not available or empty"""
        import random
        sample_pharmacies = []
        pharmacy_data = [
            {"name": "Apollo Pharmacy (Sample)", "phone": "+91-9876543210"},
            {"name": "MedPlus (Sample)", "phone": "+91-9876543211"},
            {"name": "Netmeds Store (Sample)", "phone": "+91-9876543212"},
            {"name": "HealthPlus (Sample)", "phone": "+91-9876543213"},
            {"name": "Wellness Forever (Sample)", "phone": "+91-9876543214"}
        ]
        for i, data in enumerate(pharmacy_data):
            offset_lat = random.uniform(-0.01, 0.01)
            offset_lng = random.uniform(-0.01, 0.01)
            distance = random.uniform(500, min(radius, 5000))
            sample_pharmacies.append({
                "name": data["name"],
                "address": f"Sample Address {i+1}, Local Area",
                "phone": data["phone"],
                "latitude": latitude + offset_lat,
                "longitude": longitude + offset_lng,
                "distance": distance,
                "rating": 4.5,
                "is_open_now": True,
                "source": "Sample Data"
            })
        sample_pharmacies.sort(key=lambda x: x['distance'])
        return sample_pharmacies

