import requests
import folium
import polyline
import os

class MapplsRouteViewer:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://apis.mapmyindia.com/advancedmaps/v1"
    
    def get_route(self, start_coords, end_coords):
        """
        Get route between two coordinates
        start_coords, end_coords: tuple of (lat, lng)
        """
        url = f"{self.base_url}/{self.api_key}/route_adv/driving/{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}"
        
        params = {
            'geometries': 'polyline',
            'overview': 'full'
        }
        
        response = requests.get(url, params=params)
        return response.json()
    
    def create_map(self, start_coords, end_coords, route_data):
        """
        Create a folium map with the route
        """
        # Center map between start and end points
        center_lat = (start_coords[0] + end_coords[0]) / 2
        center_lng = (start_coords[1] + end_coords[1]) / 2
        
        # Create map
        m = folium.Map(location=[center_lat, center_lng], zoom_start=10)
        
        # Add start marker
        folium.Marker(
            start_coords,
            popup="Start",
            icon=folium.Icon(color='green', icon='play')
        ).add_to(m)
        
        # Add end marker
        folium.Marker(
            end_coords,
            popup="End",
            icon=folium.Icon(color='red', icon='stop')
        ).add_to(m)
        
        # Add route if available
        if 'routes' in route_data and route_data['routes']:
            route_geometry = route_data['routes'][0]['geometry']
            decoded_coords = polyline.decode(route_geometry)
            
            folium.PolyLine(
                locations=decoded_coords,
                weight=5,
                color='blue',
                opacity=0.8
            ).add_to(m)
        
        return m

# Usage example
def main():
    # Replace with your Mappls API key
    API_KEY = os.getenv('MAPPLS_API_KEY', 'YOUR_MAPPLS_API_KEY')
    
    # Example coordinates (Bangalore to Chennai)
    start = (12.9716, 77.5946)  # Bangalore
    end = (13.0827, 80.2707)    # Chennai
    
    route_viewer = MapplsRouteViewer(API_KEY)
    
    try:
        # Get route data
        route_data = route_viewer.get_route(start, end)
        
        # Create map
        map_obj = route_viewer.create_map(start, end, route_data)
        
        # Save map
        map_obj.save("route_map.html")
        print("Route map saved as 'route_map.html'")
        
        # Print route info
        if 'routes' in route_data and route_data['routes']:
            distance = route_data['routes'][0]['distance'] / 1000  # Convert to km
            duration = route_data['routes'][0]['duration'] / 60    # Convert to minutes
            print(f"Distance: {distance:.2f} km")
            print(f"Duration: {duration:.2f} minutes")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()