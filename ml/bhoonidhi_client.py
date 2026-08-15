"""
ml/bhoonidhi_client.py
Official ISRO / NRSC Bhoonidhi OpenSearch & STAC API Client
Documentation & Endpoint: https://bhoonidhi.nrsc.gov.in/bhoonidhi-api/

Supported ISRO Sensor Collections:
  - RS2A_L4MX70  : Resourcesat-2A LISS-4 Multispectral (5.8m GSD, 70km swath)
  - RS2_L4MX70   : Resourcesat-2 LISS-4 Multispectral (5.8m GSD, 70km swath)
  - RS2A_L3      : Resourcesat-2A LISS-3 (23.5m GSD, 141km swath)
  - CARTOSAT-2S  : Cartosat-2 Series Panchromatic (0.65m GSD) / Multispectral (1.6m GSD)
"""

import os
import json
import requests
from typing import Dict, Any, List, Optional

class BhoonidhiClient:
    """
    Standardized REST client for ISRO Bhoonidhi OpenSearch / STAC services.
    """
    BASE_URL = "https://bhoonidhi.nrsc.gov.in/bhoonidhi-api"
    SEARCH_ENDPOINT = "https://bhoonidhi.nrsc.gov.in/bhoonidhi-api/opensearch/search"
    AUTH_ENDPOINT = "https://bhoonidhi.nrsc.gov.in/bhoonidhi-api/auth/token"

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None, api_key: Optional[str] = None):
        self.username = username or os.getenv("BHOONIDHI_USERNAME", "")
        self.password = password or os.getenv("BHOONIDHI_PASSWORD", "")
        self.api_key = api_key or os.getenv("BHOONIDHI_API_KEY", "")
        self.token = None

    def authenticate(self) -> Optional[str]:
        """Authenticates against Bhoonidhi API and retrieves bearer token."""
        if not self.username or not self.password:
            return None

        try:
            payload = {"username": self.username, "password": self.password}
            headers = {"Content-Type": "application/json"}
            resp = requests.post(self.AUTH_ENDPOINT, json=payload, headers=headers, timeout=15)
            if resp.status_code == 200:
                self.token = resp.json().get("access_token")
                return self.token
        except Exception as e:
            print(f"[Bhoonidhi Auth Error]: {e}")
        return None

    def search_scenes(
        self,
        bbox: List[float], # [min_lon, min_lat, max_lon, max_lat]
        start_date: str,
        end_date: str,
        collection: str = "RS2A_L4MX70",
        max_cloud_cover: float = 15.0
    ) -> Dict[str, Any]:
        """
        Queries Bhoonidhi catalog for Resourcesat-2A LISS-4 scenes over a geographic bounding box.
        """
        token = self.authenticate()
        if not token and not self.api_key:
            return {
                "authenticated": False,
                "data_source": "BHOONIDHI_UNAUTHENTICATED",
                "message": "BHOONIDHI_USERNAME / BHOONIDHI_PASSWORD or BHOONIDHI_API_KEY not configured. Register at https://bhoonidhi.nrsc.gov.in for open Indian EO data access.",
                "scenes_found": 0,
                "features": []
            }

        headers = {
            "Authorization": f"Bearer {token or self.api_key}",
            "Accept": "application/json"
        }
        params = {
            "collection": collection,
            "bbox": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
            "startDate": start_date,
            "endDate": end_date,
            "cloudCover": max_cloud_cover,
            "format": "json"
        }

        try:
            resp = requests.get(self.SEARCH_ENDPOINT, headers=headers, params=params, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "authenticated": True,
                    "data_source": "ISRO_BHOONIDHI_LIVE",
                    "scenes_found": len(data.get("features", [])),
                    "features": data.get("features", [])
                }
            else:
                return {
                    "authenticated": True,
                    "data_source": "BHOONIDHI_API_ERROR",
                    "http_status": resp.status_code,
                    "error": resp.text[:300],
                    "scenes_found": 0,
                    "features": []
                }
        except Exception as e:
            return {
                "authenticated": False,
                "data_source": "BHOONIDHI_CONNECTION_FAILED",
                "error": str(e),
                "scenes_found": 0,
                "features": []
            }