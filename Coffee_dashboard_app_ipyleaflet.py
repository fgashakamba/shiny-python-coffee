from shiny import App, render, ui, reactive
from shinywidgets import output_widget, render_widget
from ipywidgets import HTML
from ipyleaflet import Map, Marker, CircleMarker, MarkerCluster, GeoJSON, GeoData
from ipyleaflet import LayersControl, ScaleControl, Popup
import geopandas as gpd
import pandas as pd
import shinyswatch
from shapely import wkt
from shapely.geometry import Point
from geopy.distance import geodesic
import plotly.graph_objects as go
from pathlib import Path

# Load and prepare csv data
def load_data(path):
    # Load CSV data
    data_cws = pd.read_csv(f"{path}/Coffee_Washing_Stations.csv")
    data_farmers = pd.read_csv(f"{path}/Coffee_farmers.csv")
    data_farms = pd.read_csv(f"{path}/Coffee_farms.csv")

    # Convert column names to lower case
    data_cws.columns = data_cws.columns.str.lower()
    data_farmers.columns = data_farmers.columns.str.lower()
    data_farms.columns = data_farms.columns.str.lower()

    # convert farmer_cws to lower case
    data_farmers = data_farmers[data_farmers['farmer_cws'].notna()]
    data_farmers['farmer_cws'] = data_farmers['farmer_cws'].str.lower().str.replace(' ', '_')
    
    data_cws = gpd.GeoDataFrame(
        data_cws, 
        geometry=gpd.GeoSeries.from_wkt(data_cws['geom']), 
        crs="EPSG:4326"
    ).drop('geom', axis=1)
    
   # define a function to filter out farms with invalid WKT strings
    def safe_load_wkt(wkt_string):
        try:
            return wkt.loads(wkt_string)
        except Exception:
            return None

    # Apply the WKT validation function to filter out invalid geometries
    data_farms['geometry'] = data_farms['geom'].apply(safe_load_wkt)
    data_farms = data_farms[data_farms['geometry'].notnull()].copy()

    # Convert to GeoDataFrame and project to UTM to allow area calculation
    data_farms = gpd.GeoDataFrame(data_farms, geometry='geometry', crs='EPSG:4326').to_crs(epsg=32736) 

    # Calculate farm areas
    data_farms['area'] = data_farms.area / 100
    
    # Calculate centroids for farms
    data_farms['geometry'] = data_farms.geometry.centroid 
    data_farms.to_crs(epsg=4326, inplace=True)
    data_farms = data_farms.drop('geom', axis=1)
    
    # Convert columns to numeric
    data_cws['actual_capacity'] = pd.to_numeric(data_cws['actual_capacity'])
    
    return data_cws, data_farmers, data_farms

# load geometry data
def load_geo_data(path):
    country = gpd.read_file(f"{path}/RW_country.gpkg", layer="country")
    lakes = gpd.read_file(f"{path}/RW_lakes.gpkg", layer="lakes")
    parks = gpd.read_file(f"{path}/RW_national_parks.gpkg", layer="np")
    districts = gpd.read_file(f"{path}/RW_districts.gpkg", layer="districts")
    districts['district'] = districts['district'].str.lower() # Convert district names to lowercase   
    return country, lakes, parks, districts

# define app UI
app_ui = ui.page_fluid(   
ui.tags.style(
        """   
        .card > .card-body {
            padding: 0px !important;
            margin: 0px !important;
        }  
        /* map container dimensions */
        .map-container {
            height: 770px !important;
            padding: 0 !important;
            margin: 0 !important;
            width: 100%;
            overflow: hidden;
            position: relative;
            overflow: hidden !important;
            background: transparent !important;
        }
        .map-container > * {
            height: 100% !important;
                width: 100% !important;
                margin: 0 !important;
                padding: 0 !important;
        }
        
        /* bg of the map tabs headers */
        .nav-tabs.card-header-tabs {
            background-color: #e4cfb3 !important;
            border-radius: 10px 10px 0 0 !important;
        }

        /* style of the headers of map tabs */
        .nav-tabs {
            border-bottom: none !important;
            padding: 10px 10px 0 10px !important;
            background-color: #f8f9fa !important;
        }
        .nav-tabs .nav-link {
            color: #495057 !important;
            border: none !important;
            border-radius: 8px 8px 0 0 !important;
            padding: 12px 20px !important;
            margin-right: 5px !important;
            font-weight: 500 !important;
            transition: all 0.2s ease !important;
        }
        .nav-tabs .nav-link:hover:not(.active) {
            background-color: #e9ecef !important;
            border: none !important;
        }
        .nav-tabs .nav-link.active {
            background-color: #2c3e50 !important;
            color: white !important;
            border: none !important;
        }

        .card-header {
            background-color: #e4cfb3 !important;
            border-radius: 10px 10px 0 0 !important;
            padding: 10px !important;
        }

        /* Make card body flush with tabs */
        .card-body {
            padding-top: 0 !important;
            margin: 0px !important;
        }
        /* Metric cards styling */
        .metric-card, .card {
            border: none !important;
            border-radius: 10px !important;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
            transition: transform 0.2s ease-in-out !important;
            margin-bottom: 15px !important;
        }
        .metric-card:hover, .card:hover {
            transform: translateY(-3px);
        }
        .metric-card .card-header, .card .card-header {
            border-radius: 10px 10px 0 0 !important;
            padding: 5px 20px !important;
            font-size: 0.9rem !important;
            font-weight: 600 !important;
            letter-spacing: 0.5px !important;
            width: 100% !important;
            margin: 0 !important;
        }
        /* Card header colors */
        .farmers-header {
            background-color: #2c3e50 !important;
            color: white !important;
        }
        .women-header {
            background-color: #16a085 !important;
            color: white !important;
        }
        .youth-header {
            background-color: #a4d5af !important;
            color: white !important;
        }
        .hh-with-youth-header {
            background-color: #b5dfce !important;
            color: white !important;
        }
        .hh-header {
            background-color: #b9cfbe !important;
            color: white !important;
        }
        .area-header {
            background-color: #2c3e50 !important;
            color: white !important;
        }
        /* Card body styling */
        .metric-value {
            padding: 20px !important;
            text-align: center !important;
            font-size: 1.8rem !important;
            font-weight: 700 !important;
            color: #2c3e50 !important;
        }
        /* Labels and units */
        .metric-label {
            display: block;
            font-size: 0.8rem;
            color: #7f8c8d;
            margin-top: 5px;
        }
        .metric-trend {
            font-size: 0.9rem;
            color: #27ae60;
            margin-top: 5px;
        }
        .metric-trend.positive {
            color: #27ae60;
        }
        .metric-trend.negative {
            color: #e74c3c;
        }
        /* Chart card specific styling */
        .card:has(div.shiny-plot-output) {
            height: calc(33vh - 20px) !important;
            margin-bottom: 15px !important;
        }
        .card:has(div.shiny-plot-output) .card-body {
            padding: 10px !important;
            height: calc(100% - 45px) !important;
        }
        .shiny-plot-output {
            height: 100% !important;
            width: 100% !important;
        }
                
        /* Fix for specific chart panels being collapsed on initial load */
        .card:has(div.shiny-html-output#coffee_trees_chart) {
            height: 320px !important;
            margin-bottom: 15px !important;
            }

        .card:has(div.shiny-html-output#touch_points_chart) {
            height: 350px !important;
            margin-bottom: 15px !important;
            }

        /* Style for card bodies containing charts */
        .card:has(div.shiny-html-output[id$="chart"]) .card-body {
            padding: 10px !important;
            height: calc(100% - 45px) !important;
            position: relative;
            }

        /* Loading spinner for UI outputs */
        .loading-spinner-container {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(255, 255, 255, 0.7);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 1000;
            }
        .loading-spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 2s linear infinite;
            }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
            }

        /* Make sure containers are positioned relatively for absolute positioning of spinner */
        .card:has(div.shiny-html-output), .shiny-html-output {
            position: relative;
            min-height: 50px;
            }
        """
    ),
    ui.tags.script("""
        // Add spinners to all UI outputs on page load
        $(document).ready(function() {
        // Add spinners initially to all UI outputs
        $('.shiny-html-output').each(function() {
            var $this = $(this);
            $this.css('position', 'relative');
            $this.append('<div class="loading-spinner-container"><div class="loading-spinner"></div></div>');
        });
        });

        // Handle updates - remove spinner when content arrives
        $(document).on('shiny:value', function(event) {
        var $target = $('#' + event.target.id);
        $target.find('.loading-spinner-container').remove();
        });

        // Add spinner back when output is recalculating
        $(document).on('shiny:outputinvalidated', function(event) {
        var $target = $('#' + event.target.id);
        
        if ($target.hasClass('shiny-html-output')) {
            $target.css('position', 'relative');
            $target.append('<div class="loading-spinner-container"><div class="loading-spinner"></div></div>');
        }
        });
    """),
        
    ui.row(
        ui.column(12,
            ui.div(
                ui.h2("Coffee Extension Activities Dashboard"),
                ui.h4("A dashboard to track key extension-related KPIs for Rwanda's coffee program")
            )
        )
    ),
    
    ui.layout_columns(
        ui.row(
            ui.column(3, 
                ui.card(
                    ui.card_header("Total Farmers", class_="farmers-header"),
                    ui.div(
                        ui.output_text("nbr_farmers"),
                        ui.span("registered coffee farmers", class_="metric-label"),
                        class_="metric-value"
                    ),
                    class_="metric-card"
                ),
                ui.card(
                    ui.card_header("Women Participation", class_="women-header"),
                    ui.div(
                        ui.output_text("nbr_farmers_women"),
                        ui.span("of total farmers are women", class_="metric-label"),
                        #ui.div("↑ 2.3% from last season", class_="metric-trend positive"),
                        class_="metric-value"
                    ),
                    class_="metric-card"
                ),
                ui.card(
                    ui.card_header("Youth Engagement", class_="youth-header"),
                    ui.div(
                        ui.output_text("nbr_farmers_young"),
                        ui.span("of all the farmers are young", class_="metric-label"),
                        #ui.div("↑ 1.8% from last season", class_="metric-trend positive"),
                        class_="metric-value"
                    ),
                    class_="metric-card"
                ),
                ui.card(
                    ui.card_header("Youth in Households", class_="hh-header"),
                    ui.div(
                        ui.output_text("youth_in_hh"),
                        ui.span("young people in farmers' households", class_="metric-label"),
                        class_="metric-value"
                    ),
                    class_="metric-card"
                )
            ),

            # Map tabs remain the same
            ui.column(6,
                ui.navset_card_tab(
                    ui.nav_panel("CWS View",                        
                        ui.div(                                               
                            output_widget("map_cws"),
                            class_="map-container"
                        )
                    ),
                    ui.nav_panel("Coffee Farms View",
                        ui.div(
                            output_widget("map_farms"),
                            class_="map-container"
                        )
                    ), id="map_tabs" 
                )
            ),

            ui.column(3,
                ui.card(
                    ui.card_header("Total Cultivated Area", class_="area-header"),
                    ui.div(
                        ui.output_text("farm_area"),
                        ui.span("Hectares", class_="metric-label"),
                        #ui.div("↑ 3.2% from last season", class_="metric-trend positive"),
                        class_="metric-value"
                    ),
                    class_="metric-card"
                ),
                ui.card(
                    ui.card_header("# Coffee trees per age", class_="women-header"),
                    output_widget("coffee_trees_chart", height="260px")
                ),
                ui.card(
                    ui.card_header("# Farmers per training touchpoints", class_="hh-header"),
                    output_widget("touch_points_chart", height="260px")
                )
            )
        )
    ),
    # Remove spinners when the content is fully loaded
    ui.tags.script("""
        $(document).on('shiny:outputinvalidated', function(event) {
        var $target = $('#' + event.target.id);

        $(document).on('shiny:value', function(event) {
        var $target = $('#' + event.target.id);
        
        // Remove spinner if it exists
        $target.find('.loading-spinner-container').remove();
        });
        """
    ),
    theme=shinyswatch.theme.flatly
)

def server(input, output, session):
    # Load data
    current_dir = Path(__file__).parent # Get the directory of the current script
    coffee_data_path = current_dir / "data" 
    geo_data_path = current_dir / "data_wgs84"  
    country, lakes, parks, districts = load_geo_data(geo_data_path)
    data_cws, data_farmers, data_farms = load_data(coffee_data_path)
    
    #------------------------------------------------------------------
    # for demo purposes, let's assign CWS IDs from the cws dataset to the farmers
    import random
    cws_ids = data_cws['cws_id'].unique()
    data_farmers['farmer_cws'] = random.choices(cws_ids, k=len(data_farmers))
    data_farms['cws_id'] = random.choices(cws_ids, k=len(data_farms))
    #-----------------------------------------------------------------------------------

    # Display country statistics
    @output
    @render.text
    def nbr_farmers():
        return f"{len(data_farmers):,}"
    
    @output
    @render.text
    def nbr_farmers_women():
        women = len(data_farmers[data_farmers['gender'] == 'female'])
        return f"{(women / len(data_farmers)) * 100:.1f}%"
    
    @output
    @render.text
    def nbr_farmers_young():
        young = len(data_farmers[data_farmers['age'].astype(int) < 35])
        return f"{(young / len(data_farmers)) * 100:.1f}%"
    
    @output
    @render.text
    def youth_in_hh():
        return f"{data_farmers['young_in_hh'].dropna().astype(int).sum():,}" 

    # Initialize reactive values
    clicked_spot = reactive.Value(None)
    cws_map_widget = reactive.Value(None)
    farms_map_widget = reactive.Value(None)
    selected_district_layer = reactive.Value(None)
    selected_farms_layer = reactive.Value(None)
    selected_cws_layer = reactive.Value(None)

    # Calculate reactive variables used for interactivity
    #------------------------------------------------
    #1. get the clicked district
    @reactive.Calc
    def selected_district():
        pt = clicked_spot.get()
        if pt is not None:
            current_district = gpd.sjoin(districts, pt, how="inner", predicate="intersects")
            return current_district
        return None

    #2. get the farms in the selected district
    @reactive.Calc
    def selected_farms():
        cur_district = selected_district()
        if cur_district is not None:
            distr_farms = gpd.sjoin(data_farms, cur_district.loc[:, ['district', 'geometry']], how="inner", predicate="intersects")
            return distr_farms
        return None
    
    #3. Get the nearest CWS to the clicked spot on the CWS map
    @reactive.Calc
    def selected_cws():
        pt = clicked_spot.get()
        if pt is None:
            return None
            
        # Convert the point to its coordinates
        # Assuming pt is a GeoDataFrame with a single point
        point_coords = (pt.geometry.iloc[0].y, pt.geometry.iloc[0].x)
        
        # Calculate distances from clicked point to all CWS locations
        distances = data_cws.geometry.apply(
            lambda x: geodesic(
                point_coords,
                (x.y, x.x)
            ).meters
        )
        
        # Get the index of the minimum distance
        nearest_idx = distances.idxmin()
        
        # Return the nearest CWS
        return data_cws.iloc[[nearest_idx]]
    
    # Add a reactive effect to reset selected_cws and selected-district to Null 
    # This will trigger whenever the map tab changes
    @reactive.Effect
    def _reset_on_tab_change():
        input.map_tabs()
        clicked_spot.set(None)

    # Display the CWS map
    @output
    @render_widget
    def map_farms():
        # Define the map
        m = Map(center=(-1.9403, 29.8739), zoom=8, scroll_wheel_zoom=True)

        # Create the layers with names that will appear in the LayersControl
        country_style = {
            'fillColor': '#acbbb4', 
            'color': '#3f4b46',   
            'weight': 4,     
            'fillOpacity': 0.2
        }
        country_layer = GeoData(
            geo_dataframe=country, 
            style=country_style,
            name='Country boundary'
        )

        parks_style = {
            'fillColor': '#13764b',  
            'color': '#006600',   
            'weight': 2,     
            'fillOpacity': 0.6
        }
        parks_layer = GeoData(
            geo_dataframe=parks, 
            style=parks_style,
            name='National parks'
        )

        lakes_style = {
            'fillColor': '#37a3bd', 
            'color': '#345a6a',   
            'weight': 1,     
            'fillOpacity': 0.6
        }
        lakes_layer = GeoData(
            geo_dataframe=lakes,
            style=lakes_style,
            name='Lakes'
        )
        districts_style = {
                'fillColor': '#acbbb4',
                'color': '#3f4b46',  
                'weight': 2,    
                'fillOpacity': 0.2
            }
        
        districts_layer = GeoData(
            geo_dataframe=districts,
            style=districts_style,
            hover_style={'fillColor': '#bcb32e' , 'fillOpacity': 0.9},
            name='District boundaries'
        )

        # Convert farms geodataframe to GeoJSON format
        farms_json = data_farms.__geo_interface__

        farms_style = {
            'fillColor': '#171c1a',
            'fillOpacity': 0.6,
            'radius': 6,  # Fixed radius instead of depending on zoom level
            'color': '#6d7471',
        }
        farms_layer = GeoJSON(
            data=farms_json, 
            point_style=farms_style,
            hover_style={'fillOpacity': 0.9},
            marker_type='circle', 
            name='Coffee farms'
        )

        # Add clusters of farms
        markers = []
        for feature in farms_json['features']:
            coords = feature['geometry']['coordinates']  # of each farm centroid
            lat_lon = (coords[1], coords[0]) # Convert the coords to (lat, lon)
            marker = Marker(location=lat_lon) # Create a Marker for each farm
            markers.append(marker)

        # Create a MarkerCluster and add the markers
        marker_cluster = MarkerCluster(markers=markers)
        marker_cluster.name = "Farm clusters"

        # Add the MarkerCluster to the map
        m.add_layer(marker_cluster)
                
        # Add the districts layer to the map
        m.add_layer(country_layer)
        m.add_layer(lakes_layer)
        m.add_layer(parks_layer)
        m.add_layer(districts_layer)
        m.add_layer(farms_layer)
        
        # Add layers control
        layer_control = LayersControl(position='topright')
        m.add_control(layer_control)

        # Add scale control
        scale = ScaleControl(position='bottomleft')
        m.add_control(scale)

        def handle_click(**kwargs):
            if kwargs.get("type") == "click":
                lat, lng = kwargs.get("coordinates")
                
                # Create a GeoPandas point
                point = gpd.GeoDataFrame(
                    [{"geometry": Point(lng, lat)}],
                    crs="EPSG:4326"
                )
                
                # Update the clicked spot
                clicked_spot.set(point)

        # Attach the click handler to the map
        m.on_interaction(handle_click)
        
        # Store map widget
        farms_map_widget.set(m)

        return m

    # add the selected district to the map
    @reactive.Effect
    @reactive.event(selected_district)
    def _():
        m = farms_map_widget.get()
        cur_district = selected_district()
        
        if m is None:
            return
            
        # Remove previous selected district layer if it exists
        old_layer = selected_district_layer.get()
        if old_layer is not None:
            try:
                m.remove_layer(old_layer)
            except Exception:
                pass  # Layer might have been already removed
        
        # Clear the old layer reference
        selected_district_layer.set(None)
        
        if cur_district is not None and not cur_district.empty:
            # Create a new GeoJSON layer for the selected district
            selected_district_style = {
                'color': 'red',
                'fillColor': 'yellow',
                'opacity': 0.8,
                'weight': 2
            }
            
            # Create and add the new layer
            new_layer = GeoData(
                geo_dataframe=cur_district, 
                style=selected_district_style,
                name='Selected District'  
            )
            m.add_layer(new_layer)
            
            # Store the new layer reference
            selected_district_layer.set(new_layer)

    # highlight farms in the selected district
    @reactive.Effect
    @reactive.event(selected_farms)
    def _():
        m = farms_map_widget.get()
        cur_farms = selected_farms()
        
        if m is None:
            return
            
        # Remove previous selected farms layer if it exists
        old_layer = selected_farms_layer.get()
        if old_layer is not None:
            try:
                m.remove_layer(old_layer)
            except Exception:
                pass 
        
        # Clear the old layer reference
        selected_farms_layer.set(None)
        
        if cur_farms is not None and not cur_farms.empty:
            # Create a new GeoJSON layer for the selected farms
            selected_farms_style = {
                'fillColor': '#b8b242',
                'fillOpacity': 0.6,
                'radius': 3,  
                'color': 'yellow'
            }

            # Convert the selected district to GeoJSON
            selected_farms_json = cur_farms.__geo_interface__

            # Create and add the new layer
            new_layer = GeoJSON(
                data=selected_farms_json, 
                point_style=selected_farms_style,
                hover_style={'fillOpacity': 0.9},
                name='Selected farms'  
            )
            m.add_layer(new_layer)
            
            # Store the new layer reference
            selected_farms_layer.set(new_layer)

    # Display the farms on the map
    @output
    @render_widget
    def map_cws():        
        # Define the map with bounds instead of center/zoom
        m = Map(center=(-1.9403, 29.8739), zoom=8, scroll_wheel_zoom=True, close_popup_on_click=True)
        
        # Create the layers (country, lakes, parks remain the same)
        country_style = {
            'fillColor': '#acbbb4',
            'color': '#3f4b46',  
            'weight': 4,    
            'fillOpacity': 0.2
        }
        country_layer = GeoData(
            geo_dataframe =country,
            style=country_style,
            name='Country boundary'
        )
        
        parks_style = {
            'fillColor': '#13764b',  
            'color': '#006600',  
            'weight': 2,    
            'fillOpacity': 0.6
        }
        parks_layer = GeoData(
            geo_dataframe=parks,
            style=parks_style,
            name='National parks'
        )
        
        lakes_style = {
            'fillColor': '#37a3bd',
            'color': '#345a6a',  
            'weight': 1,    
            'fillOpacity': 0.6
        }
        lakes_layer = GeoData(
            geo_dataframe=lakes,
            style=lakes_style,
            name='Lakes'
        )

        districts_style = {
                'fillColor': '#acbbb4',
                'color': '#3f4b46',  
                'weight': 2,    
                'fillOpacity': 0.2
            } 
        districts_layer = GeoData(
            geo_dataframe=districts,
            style=districts_style,
            hover_style={'fillColor': '#bcb32e' , 'fillOpacity': 0.2},
            name='District boundaries'
        )

        # Convert CWS data to GeoJSON for display
        cws_json = data_cws.__geo_interface__
        
        # define a function to add CWS markers with tooltips
        def add_cws_markers(map_obj, data_json):
            markers = [] # initialize a list to store the markers
            for feature in data_json['features']:
                properties = feature['properties']
                coordinates = feature['geometry']['coordinates']
                
                capacity = int(properties.get('actual_capacity', 0))
                ownership = properties.get('cws_ownership', 'unknown').lower()
                name = properties.get('cws_name', 'N/A')
                
                ownership_colors = {
                    'cooperative': '#4daf4a',
                    'other_entity': '#377eb8',
                }
                
                min_radius = 3
                max_radius = 8
                scaling_factor = 0.001
                
                # Create marker with tooltip as a plain string
                marker = CircleMarker(
                    location=(coordinates[1], coordinates[0]),
                    radius=int(min(min_radius + (capacity * scaling_factor), max_radius)),
                    fill_color=ownership_colors.get(ownership, '#808080'),
                    fill_opacity=0.6,
                    color='black',
                    weight=1
                )
                
                #Create detailed popup for click events
                popup_html = f"""
                <div style='font-family: Arial, sans-serif; padding: 3px; margin: 0; line-height: 1.2;'>
                    <div><b>Name:</b> {name}</div>
                    <div><b>Capacity:</b> {capacity} Tonnes</div>
                    <div><b>Ownership:</b> {ownership.title()}</div>
                </div>
                """
                popup = Popup(
                    location=(coordinates[1], coordinates[0]),
                    child=HTML(value=popup_html),
                    close_button=True,
                    auto_close=True,
                    close_on_escape_key=True
                )

                # bind the popup to the marker
                marker.popup = popup

                # # Create a simple name-tooltip defined as a popup
                tooltip_html = f"""
                    <div style='font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif; 
                                padding: 3px; 
                                margin: 0;
                                line-height: 1.2; 
                                color: #313723; 
                                border-radius: 5px; 
                                font-size: 12px;'>
                        <div><b>Name:</b> {name}</div>
                    </div>
                """
                tooltip = Popup(
                    location=(coordinates[1], coordinates[0]),
                    child=HTML(tooltip_html),
                    close_button=False,
                    auto_close=True,
                    close_on_escape_key=True
                )

                # Functions to add and remove tooltip-like popup
                def create_mouseover_func(tooltip):
                    def on_mouse_over(event, **kwargs):
                        map_obj.add_layer(tooltip)
                    return on_mouse_over

                def create_mouseout_func(tooltip):
                    def on_mouse_out(event, **kwargs):
                        map_obj.remove_layer(tooltip)
                    return on_mouse_out
                
                marker.on_mouseover(create_mouseover_func(tooltip))
                marker.on_mouseout(create_mouseout_func(tooltip))
                
                markers.append(marker)
            
            # create a layer group for the markers
            marker_group = MarkerCluster(markers=markers, 
                                         max_cluster_radius=20,
                                         name='Coffee Washing Stations')

            # add the marker group to the map
            map_obj.add_layer(marker_group)

        # # define a function to add labels to districts
        # def add_distr_labels(map_widget, distr_data, min_zoom=8):
        #     markers = []
            
        #     for idx, row in distr_data.iterrows():
        #         label = row['district']
        #         geometry = row['geometry'].centroid
        #         label_icon = DivIcon(
        #             html=f'''
        #                 <div class="leaflet-div-icon" style="
        #                     font-size: 14px;
        #                     font-weight: bold;
        #                     font-color: #a59e0d;
        #                     background: none;
        #                     border: none;
        #                     box-shadow: none;
        #                     pointer-events: none;
        #                     white-space: nowrap;
        #                     transform: translate(-50%, -50%);
        #                     color: black;
        #                 ">
        #                     {label}
        #                 </div>
        #             ''',
        #             icon_size=(0, 0),
        #             icon_anchor=(0, 0),
        #             class_name='transparent-div-icon',
        #             bg_pos=None
        #         )
        #         marker = Marker(location=(geometry.y, geometry.x), icon=label_icon, draggable=False)
        #         map_widget.add_layer(marker)
        #         markers.append(marker)
            
        #     # Remove the labels when zoomed id beyond the set minimum zoom level
        #     def on_zoom_change(change):
        #         current_zoom = change.new  # Get the new zoom level from the change event
                
        #         for marker in markers:
        #             if current_zoom < min_zoom:
        #                 try:
        #                     map_widget.remove_layer(marker)
        #                 except:
        #                     pass
        #             else:
        #                 if marker not in map_widget.layers:
        #                     map_widget.add_layer(marker)
            
        #     # Observe the zoom property changes
        #     map_widget.observe(on_zoom_change, names='zoom')
            
        #     return markers

        # # The the labels to the map as a layer
        # add_distr_labels(m, districts)

       
        # Add layers to the map
        m.add_layer(country_layer)
        m.add_layer(lakes_layer)
        m.add_layer(parks_layer)
        m.add_layer(districts_layer)
              
        # Add CWS markers and districts labels
        add_cws_markers(m, cws_json)
        
        # Add controls
        layer_control = LayersControl(position='topright')
        m.add_control(layer_control)
        
        scale = ScaleControl(position='bottomleft')
        m.add_control(scale)
        
        def handle_click(**kwargs):
            if kwargs.get("type") == "click":
                lat, lng = kwargs.get("coordinates")
                point = gpd.GeoDataFrame(
                    [{"geometry": Point(lng, lat)}],
                    crs="EPSG:4326"
                )
                clicked_spot.set(point)

        m.on_interaction(handle_click)
        cws_map_widget.set(m)
        
        return m
    
    # highlight the nearest CWS to the clicked spot
    @reactive.Effect
    @reactive.event(selected_cws)
    def _():
        m = cws_map_widget.get()
        cur_cws = selected_cws()
        
        if m is None:
            return
            
        # Remove previous selected farms layer if it exists
        old_layer = selected_cws_layer.get()
        if old_layer is not None:
            try:
                m.remove_layer(old_layer)
            except Exception:
                pass 
        
        # Clear the old layer reference
        selected_cws_layer.set(None)
        
        if cur_cws is not None and not cur_cws.empty:
            # Create a new GeoJSON layer for the selected farms
            selected_cws_style = {
                'fillColor': '#b8b242',
                'fillOpacity': 0.6,
                'radius': 3,  
                'color': 'yellow'
            }

            # Convert the selected district to GeoJSON
            selected_cws_json = cur_cws.__geo_interface__

            # Create and add the selected CWS layer
            new_layer = GeoJSON(
                data=selected_cws_json, 
                point_style=selected_cws_style,
                hover_style={'fillOpacity': 0.9},
                name='Selected CWS'  
            )
            m.add_layer(new_layer)
            
            # Store the new layer reference
            selected_cws_layer.set(new_layer)

    # Calculate and reactive variables and update related charts
    #==========================================================
    #1. Farm area info card
    @output
    @render.text
    def farm_area():
        current_tab = input.map_tabs()
        if current_tab == "Coffee Farms View":
            if selected_district() is not None:
                # Perform spatial join if a district is selected
                filtered_farms = gpd.sjoin(data_farms, selected_district().loc[:, ['district', 'geometry']], how="inner", predicate="intersects")
                total_area = filtered_farms['area'].sum()
            else:
                total_area = data_farms['area'].sum()
        elif current_tab == "CWS View":
            if selected_cws() is not None:
                cur_cws = str(selected_cws()['cws_id'].values[0])
                data_farmers_cws = data_farmers[data_farmers['farmer_cws'] == cur_cws]
                unique_national_ids = data_farmers_cws['national_id'].unique().tolist()
                filtered_farms = data_farms[data_farms['national_id'].isin(unique_national_ids)]
                total_area = filtered_farms['area'].sum()
            else:
                total_area = data_farms['area'].sum()
        else:
            total_area = data_farms['area'].sum()

        return f"{total_area:,.1f}" 

    # #2. Coffee trees chart
    @output
    @render_widget
    def coffee_trees_chart():
        # filter farms data based on the active tab and/or selected district-selected CWS
        current_tab = input.map_tabs()
        if current_tab == "Coffee Farms View":
            if selected_district() is not None:
                # Perform spatial join if a district is selected
                data_farms_filtered = gpd.sjoin(data_farms, selected_district().loc[:, ['district', 'geometry']], how="inner", predicate="intersects")
            else:
                data_farms_filtered = data_farms
        elif current_tab == "CWS View":
            if selected_cws() is not None:
                cur_cws = str(selected_cws()['cws_id'].values[0])
                data_farmers_cws = data_farmers[data_farmers['farmer_cws'] == cur_cws]
                unique_national_ids = data_farmers_cws['national_id'].unique().tolist()
                data_farms_filtered = data_farms[data_farms['national_id'].isin(unique_national_ids)]
            else:
                data_farms_filtered = data_farms
        else:
            data_farms_filtered = data_farms

        # Prepare the data for ploting
        data = data_farms_filtered.groupby('age_range_coffee_trees')['nbr_coffee_trees'].sum().reset_index()
        
        # Create the plot using plotly
        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=data['age_range_coffee_trees'],
            y=data['nbr_coffee_trees'],
            marker=dict(
                color='rgba(50, 171, 96, 0.6)',
                showscale=False,
                colorbar=dict(title='age_range_coffee_trees')
            )
        ))

        # re-arrange the bars in the proper trees' age groups order
        fig.update_layout(
            xaxis = dict(
                categoryorder='array',
                categoryarray=["less_3", "3_to_7", "8_to_15", "16_to_30", "more_30"]
            ),
            height=250,
            margin=dict(l=10, r=10, t=30, b=10),
            autosize=True,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        return fig

    # 3. training chart  
    @output
    @render_widget 
    def touch_points_chart():
        # filter farmers data based on the active tab and/or selected district-selected CWS
        current_tab = input.map_tabs()
        if current_tab == "Coffee Farms View":
            if selected_district() is not None:
                # Select the farmers in the selected district
                cur_district = str(selected_district()['district'].values[0])
                data_farmers_filtered = data_farmers[data_farmers['district'] == cur_district]
            else:
                data_farmers_filtered = data_farmers
        elif current_tab == "CWS View":
            if selected_cws() is not None:
                cur_cws = str(selected_cws()['cws_id'].values[0])
                data_farmers_filtered = data_farmers[data_farmers['farmer_cws'] == cur_cws]
            else:
                data_farmers_filtered = data_farmers
        else:
            data_farmers_filtered = data_farmers

        # Prepare the training data
        training_data = (
            data_farmers_filtered['training_topics']
            .str.split(' ')
            .explode()
            .value_counts()
            .reset_index()
        )
        # Rename columns for clarity
        training_data.columns = ['topic', 'count'] 
        data = training_data.sort_values('count', ascending=False)
       
        # Create the plotly plot
        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=data['topic'],
            y=data['count'],
            marker=dict(
                color='rgba(50, 171, 96, 0.6)',
                colorscale='Greens',
                showscale=False,
                colorbar=dict(title='topic')
            )
        ))

        fig.update_layout(
            yaxis=dict(tickformat=','),
            xaxis=dict(tickangle=45),
            height=250,
            margin=dict(l=10, r=10, t=30, b=10),
            autosize=True,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )

        return fig


app = App(app_ui, server)