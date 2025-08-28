# Smartcar Auth Tracker + Mango Display Sender
# Requirements: requests
# Install with: pip install requests

import webbrowser
import http.server
import socketserver
import threading
import urllib.parse as urlparse
import requests
import json
import os
import webbrowser

# === Replace these with your actual Smartcar Developer values ===
CLIENT_ID = "d823ee77-4bb1-47e0-90a9-2b36d0220ec1"
CLIENT_SECRET = "b5add562-31a0-403f-8b2a-70607efe09e1"
REDIRECT_URI = "http://localhost:8000/callback"
SCOPE = ["read_vehicle_info", "read_location", "read_odometer"]

# Auth URL and Token Endpoint
AUTH_URL = (
    "https://connect.smartcar.com/oauth/authorize"
    f"?response_type=code"
    f"&client_id={CLIENT_ID}"
    f"&redirect_uri={REDIRECT_URI}"
    f"&scope={'%20'.join(SCOPE)}"
)
TOKEN_URL = "https://auth.smartcar.com/oauth/token"

# Handle callback code from Smartcar
def start_server(code_holder):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if "/callback" in self.path:
                query = urlparse.urlparse(self.path).query
                params = urlparse.parse_qs(query)
                code_holder["code"] = params["code"][0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Authorization complete. You can close this window.")
            else:
                self.send_error(404)

    with socketserver.TCPServer(("localhost", 8000), Handler) as httpd:
        httpd.handle_request()

# Start auth flow
code_holder = {}
thread = threading.Thread(target=start_server, args=(code_holder,))
thread.daemon = True
thread.start()

print("Opening Smartcar login page...")
webbrowser.open(AUTH_URL)
thread.join()

# Exchange code for access token
code = code_holder.get("code")
token_payload = {
    "grant_type": "authorization_code",
    "code": code,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI
}
response = requests.post(TOKEN_URL, data=token_payload)
tokens = response.json()
access_token = tokens.get("access_token")

# Get all vehicle IDs
vehicles_response = requests.get(
    "https://api.smartcar.com/v2.0/vehicles",
    headers={"Authorization": f"Bearer {access_token}"}
)
vehicles_data = vehicles_response.json()
vehicle_ids = vehicles_data.get("vehicles", [])

if not vehicle_ids:
    print("No vehicles found linked to this account.")
    exit()

# Fetch data for each vehicle
markers = []
for vehicle_id in vehicle_ids:
    info_response = requests.get(
        f"https://api.smartcar.com/v2.0/vehicles/{vehicle_id}",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    vehicle_info = info_response.json()

    location_response = requests.get(
        f"https://api.smartcar.com/v2.0/vehicles/{vehicle_id}/location",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    location = location_response.json()

    if "latitude" in location and "longitude" in location:
        lat = location["latitude"]
        lon = location["longitude"]
        name = f"{vehicle_info.get('year', '?')} {vehicle_info.get('make', '?')} {vehicle_info.get('model', '?')}"
        print(f"{name} Location:\nLatitude: {lat}, Longitude: {lon}")
        markers.append((name, lat, lon))
    else:
        print(f"Vehicle {vehicle_id} location not available: {location}")

# Generate map with all vehicles
if markers:
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Truck Locations</title>
        <meta charset='utf-8'>
        <style> html, body, #map { height: 100%; margin: 0; } </style>
        <link rel='stylesheet' href='https://unpkg.com/leaflet/dist/leaflet.css'/>
        <script src='https://unpkg.com/leaflet/dist/leaflet.js'></script>
    </head>
    <body>
        <div id='map'></div>
        <script>
            var map = L.map('map').setView([37.5, -95.7], 4);  // Centered US
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19
            }).addTo(map);
    """
    for name, lat, lon in markers:
        html_content += f"L.marker([{lat}, {lon}]).addTo(map).bindPopup('{name}');\n"

    html_content += """
        </script>
    </body>
    </html>
    """
    with open("vehicle_locations.html", "w") as f:
        f.write(html_content)

    print("Map saved to vehicle_locations.html")
    webbrowser.open("vehicle_locations.html")
else:
    print("No valid location data available for any vehicle.")
