#~~~~~~~~~~~~~~~~~~~~~~~~~~UI~~~~~~~~~~~~~~~~~~~~~~~~~~#
import streamlit as st
import pandas as pd
import sqlite3
import re
import folium
from streamlit_folium import st_folium

#IMPORTING FUNCTIONS AND CONSTANTS
from recommender import (
    get_vacation_recommendations,
    get_emigration_recommendations,
    WEATHER_SCALE,
    ALL_ATTRACTION_GROUPS
)

#WELCOME PAGE
st.set_page_config(page_title="Travel Recommender", page_icon="✈️", layout="wide")

# --- Preset Dictionaries ---
VACATION_PRESETS = {
    "Balanced": { 'weather': 0.25, 'budget': 0.15, 'attractions_quantity': 0.10, 'attractions_quality': 0.15, 'safety': 0.10, 'attractions_popularity': 0.05, 'english_level': 0.05, 'known_languages': 0.05, 'distance': 0.05, 'cuisine_quality': 0.10 },
    "Budget Explorer": { 'weather': 0.4, 'budget': 0.5, 'attractions_quantity': 0.1, 'attractions_quality': 0.05, 'safety': 0.1, 'attractions_popularity': 0.0, 'english_level': 0.0, 'known_languages': 0.0, 'distance': 0.1, 'cuisine_quality': 0.05 },
    "Culture & Cuisine Connoisseur": { 'weather': 0.1, 'budget': 0.0, 'attractions_quantity': 0.2, 'attractions_quality': 0.4, 'safety': 0.05, 'attractions_popularity': 0.1, 'english_level': 0.0, 'known_languages': 0.0, 'distance': 0.0, 'cuisine_quality': 0.4 },
    "Off-Grid Adventurer": { 'weather': 0.3, 'budget': 0.1, 'attractions_quantity': 0.3, 'attractions_quality': 0.1, 'safety': 0.3, 'attractions_popularity': -0.5, 'english_level': 0.0, 'known_languages': 0.0, 'distance': 0.1, 'cuisine_quality': 0.0 }
}

EMIGRATION_PRESETS = {
    "Balanced": { 'cost_of_living': 0.20, 'purchasing_power': 0.20, 'safety': 0.10, 'english_level': 0.10, 'hdi': 0.10, 'unemployment': 0.10, 'inflation': 0.05, 'life_expectancy': 0.05, 'distance': 0.05, 'weather': 0.05, 'known_languages': 0.0 },
    "Young Professional": { 'cost_of_living': 0.15, 'purchasing_power': 0.4, 'safety': 0.05, 'english_level': 0.15, 'hdi': 0.05, 'unemployment': 0.2, 'inflation': 0.0, 'life_expectancy': 0.0, 'distance': 0.0, 'weather': 0.0, 'known_languages': 0.0 },
    "The Family": { 'cost_of_living': 0.2, 'purchasing_power': 0.1, 'safety': 0.3, 'english_level': 0.05, 'hdi': 0.2, 'unemployment': 0.05, 'inflation': 0.1, 'life_expectancy': 0.2, 'distance': 0.0, 'weather': 0.0, 'known_languages': 0.0 },
    "Digital Nomad": { 'cost_of_living': 0.5, 'purchasing_power': 0.0, 'safety': 0.2, 'english_level': 0.1, 'hdi': 0.0, 'unemployment': 0.0, 'inflation': 0.1, 'life_expectancy': 0.0, 'distance': 0.0, 'weather': 0.1, 'known_languages': 0.0 }
}

# --- Słownik z opisami kategorii ---
ATTRACTION_DESCRIPTIONS = {
    "Historic_Heritage": "Castles, ruins, historic sites, monuments, and museums focused on history.",
    "Religion": "Churches, cathedrals, mosques, synagogues, and other religious sites.",
    "Nature_Recreation": "Parks, gardens, beaches, mountains, hiking trails, lakes, and other natural landscapes.",
    "Culture_Art": "Art museums, galleries, architectural buildings, theaters, operas, and cultural events.",
    "Museums": "A general category for all types of museums (art, history, science, specialty).",
    "Entertainment_Leisure": "Theme parks, zoos, aquariums, casinos, nightlife, and spas.",
    "Shopping_Urban": "Malls, street markets, famous streets, squares, and distinct neighborhoods.",
    "Food_Drink": "Wineries, breweries, distilleries, and food markets.",
    "Winter_Sports": "Ski and snowboard resorts and areas.",
    "Scenic_Transport": "Scenic railways, cable cars, ferries, and bridges.",
    "Science_Technology": "Science museums, observatories, and sites of technological interest.",
    "Beach": "Specifically sandy or pebble beaches for recreation.",
    "Mountains_and_trails": "Mountain ranges, hiking trails, and related activities.",
    "Landmark": "Famous points of interest, towers, observation decks, and iconic structures."
}


# --- Helper functions to load data from DB ---
@st.cache_data
def load_data():
    """Loads all necessary data from the database once."""
    try:
        conn = sqlite3.connect("travel_recommendation_final.db")
        df_dest = pd.read_sql_query("SELECT * FROM destinations", conn)
        conn.close()
        # Handle the different possible names for the 'Country' column
        country_col_name = 'Country_x' if 'Country_x' in df_dest.columns else 'Country'
        df_dest.rename(columns={country_col_name: 'Country'}, inplace=True, errors='ignore')
        return df_dest
    except Exception as e:
        st.error(f"FATAL ERROR: Could not load data from the database. Please ensure 'travel_recommendation_final.db' exists. Error: {e}")
        return pd.DataFrame()

@st.cache_data
def get_language_list(data):
    """Loads a unique, sorted list of languages from the dataframe."""
    if 'Language' in data.columns:
        return sorted([lang for lang in data['Language'].unique() if pd.notna(lang) and lang])
    return ['SOMETHING WENT WRONG']

@st.cache_data
def get_countries_and_destinations(data):
    #COUNTRIES AND DESTINATIONS
    if 'Destination' in data.columns and 'Country' in data.columns:
        df = data[['Destination', 'Country']].dropna().drop_duplicates()
        df['formatted_destination'] = df['Country'] + " - " + df['Destination']
        destinations = sorted(df['formatted_destination'].unique())
        countries = sorted(df['Country'].unique())
        return countries, destinations
    return ['STH WENT WRONG', 'STH WENT WRONG'], ['STH WENT WRONG', 'STH WENT WRONG']

# --- Chatbot Logic ---
def find_entity_in_question(question, entity_list):
    """Finds a known entity (destination or country) in the user's question."""
    question_lower = question.lower()
    # Search for longer names first to avoid partial matches (e.g., 'rome' in 'romania')
    for entity in sorted(entity_list, key=len, reverse=True):
        if entity.lower() in question_lower:
            return entity
    return None

def get_chatbot_response(question, data, all_destinations, all_countries, all_months):
    """The main chatbot logic function."""
    question_lower = question.lower().strip()
    # For entity matching, we need the raw names, not the formatted "Country - Destination"
    raw_destinations = [d.split(' - ')[-1] for d in all_destinations]
    destination = find_entity_in_question(question, raw_destinations)
    country = find_entity_in_question(question, all_countries) if not destination else None
    if any(word in question_lower for word in ["hello", "hi", "hey"]):
        return """
        Hello! I'm your travel assistant. I can help you with a few things:
        - **Find data**: Ask me "What is the HDI for Germany?" or "Weather in Rome in May?".
        - **Explain concepts**: Ask me "How do weights work?" or "What is HDI?".
        - **Find deals & info**: Ask me "Show me flights to Paris" or "Find hotels in Barcelona" or "Tell me about Warsaw".
        """

    # Rule: How weights work
    if "how do weights work" in question_lower:
        return "The weights are like sliders on a DJ's mixing console. A higher weight gives a factor more influence on the final recommendation score, allowing you to tailor the results to what's most important to you."

    # Rule: How the model works
    if "how does the model work" in question_lower:
        return "The model uses a Weighted Scoring System. For each destination, it calculates a score (from 0 to 1) for various factors like weather, budget, and safety. Each score is then multiplied by its user-defined weight. The final score is the sum of all these weighted scores, and the top 10 destinations are recommended."

    entity = destination if destination else country
    if entity:
        if destination:
            entity_data = data[data['Destination'] == entity]
        else: # country
            entity_data = data[data['Country'] == entity]

        if entity_data.empty:
            return f"Sorry, I couldn't find any data for {entity}."

        # Rule: Data lookup from the database
        data_keywords = {
            "hdi": ("HDI_Value_Latest", ".3f"),
            "safety": ("Safety_Index", ".2f"),
            "cost of living": ("CostofLivingPlusRentIndex", ".2f"),
            "purchasing power": ("LocalPurchasingPowerIndex", ".2f"),
            "unemployment": ("Unemployment_Rate_National_Latest_Pct", ".2f"),
            "inflation": ("Inflation_Rate_National_Latest_Pct", ".2f"),
            "life expectancy": ("Life_Expectancy", ".2f"),
            "cuisine rank": ("Cuisine_Rank", ".0f")
        }

        for keyword, (col, fmt) in data_keywords.items():
            if keyword in question_lower and col in entity_data.columns:
                value = pd.to_numeric(entity_data[col], errors='coerce').mean()
                return f"The average {keyword.replace('_', ' ')} for **{entity}** is: **{value:{fmt}}**."

        if "weather" in question_lower:
            for month in all_months:
                if month.lower() in question_lower:
                    month_abbr = month[:3].capitalize()
                    if month_abbr in entity_data.columns:
                        weather = entity_data[month_abbr].iloc[0]
                        return f"The weather in **{entity}** in {month} is typically **{weather}**."
            return "Please specify a month to get the weather forecast (e.g., 'weather in Paris in July')."
        
        # Rule: Link generation
        if "flight" in question_lower:
            url = f"https://www.google.com/flights?q=flights+from+Lodz+to+{entity.replace(' ', '+')}"
            return f"Sure, here is a link to search for flights to {entity}:\n[Click here for flights]({url})"
        
        if "hotel" in question_lower:
            url = f"https://www.booking.com/searchresults.html?ss={entity.replace(' ', '+')}"
            return f"Of course, here is a link to search for hotels in {entity}:\n[Click here for hotels]({url})"
        
        if "tell me about" in question_lower or "wikipedia" in question_lower:
            url = f"https://en.wikipedia.org/wiki/{entity.replace(' ', '_')}"
            return f"Here is the Wikipedia page for {entity}:\n[Read more on Wikipedia]({url})"

    # Default response
    return "Sorry, I don't understand that question. Try asking 'help' to see what I can do."

def display_recommendations(recommendations_df, all_data_df):
    """Formats and displays the recommendation dataframe and a map."""
    if recommendations_df is not None and not recommendations_df.empty:
        col1, col2 = st.columns([4, 3])

        with col1:
            st.subheader("Top 10 Recommendations")
            recs_to_display = recommendations_df.copy()
            if 'Country_x' in recs_to_display.columns:
                recs_to_display.rename(columns={'Country_x': 'Country'}, inplace=True)
            recs_to_display.insert(0, 'Rank', range(1, 1 + len(recs_to_display)))
            def highlight_top3(row):
                if row.Rank <= 3:
                    return ['background-color: #d4edda'] * len(row)
                return [''] * len(row)
            st.dataframe(recs_to_display.style.apply(highlight_top3, axis=1), hide_index=True)

        with col2:
            st.subheader("Map of Recommendations")
            lat_col = next((col for col in all_data_df.columns if 'latitude' in col.lower()), None)
            lon_col = next((col for col in all_data_df.columns if 'longitude' in col.lower()), None)

            if lat_col and lon_col:
                map_data = pd.merge(recs_to_display, all_data_df[['Destination', lat_col, lon_col]], on='Destination', how='left')
                map_data[lat_col] = pd.to_numeric(map_data[lat_col], errors='coerce')
                map_data[lon_col] = pd.to_numeric(map_data[lon_col], errors='coerce')
                map_data.dropna(subset=[lat_col, lon_col], inplace=True)
                
                if not map_data.empty:
                    m = folium.Map(location=[map_data[lat_col].mean(), map_data[lon_col].mean()], zoom_start=4)
                    for idx, row in map_data.iterrows():
                        icon_html = f'''<div style="font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 14px; font-weight: bold; color: white; background-color: #007BFF; border: 2px solid white; border-radius: 50%; width: 28px; height: 28px; text-align: center; line-height: 24px; box-shadow: 2px 2px 4px rgba(0,0,0,0.5);">{row['Rank']}</div>'''
                        folium.Marker(
                            location=[row[lat_col], row[lon_col]],
                            popup=f"#{row['Rank']}: {row['Destination']}",
                            tooltip=f"#{row['Rank']}: {row['Destination']}",
                            icon=folium.DivIcon(html=icon_html)
                        ).add_to(m)
                    st_folium(m, width=700, height=450)
                else:
                    st.warning("Could not display map - coordinate data is missing for recommendations.")
            else:
                st.warning("Could not find latitude/longitude columns in the database to display the map.")
    else:
        st.error("No recommendations found for the given criteria.")


# --- Main App ---
st.title('Personal Travel Recommender')
main_df = load_data()
if not main_df.empty:
    st.sidebar.header('Define Your Preferences')
    language_options = get_language_list(main_df)
    country_options, destination_options = get_countries_and_destinations(main_df)
    month_options = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    
    #EMIGRATION OR VACATION
    mode = st.sidebar.radio("Choose your goal:", ('Vacation', 'Emigration'))
    
    #PLACE EXCLUSION
    st.sidebar.subheader("Exclude Places", help="You can exclude entire countries or specific destinations from the recommendations.")
    excluded_countries = st.sidebar.multiselect('Exclude entire countries:', options=country_options)
    excluded_destinations_formatted = st.sidebar.multiselect('Exclude specific destinations:', options=destination_options)
    excluded_destinations = [d.split(' - ')[-1] for d in excluded_destinations_formatted]
    final_excluded_list = excluded_countries + excluded_destinations

    if mode == 'Vacation':
        st.header("Vacation Recommendations")
        with st.sidebar:
            #SIDEBARS FOR VACATION
            st.subheader("Main Preferences", help="These are the main criteria that will influence the recommendations.")
            month_pref = st.selectbox('Select month of travel:', options=month_options, index=6, help="The model will search for destinations with the best weather in your chosen month.")
            weather_pref = st.selectbox('What kind of weather are you looking for?', options=WEATHER_SCALE, index=5, help="Select your ideal weather. Destinations with similar weather will get more points.")
            budget_pref = st.select_slider('Select your budget:', options=['Budget', 'MidRange', 'Luxury'], value='MidRange', help="This is based on the average daily cost for a tourist, including accommodation, food, and attractions.")
            
            help_text_lines = ["**'everything'**: Considers all attractions, prioritizing destinations with the highest quantity and quality of attractions overall.\n\n**Category Descriptions:**\n"]
            for group, description in ATTRACTION_DESCRIPTIONS.items():
                help_text_lines.append(f"- **{group.replace('_', ' ')}:** {description}")
            attraction_help_text = "\n".join(help_text_lines)

            attraction_pref = st.multiselect(
                'What types of attractions are you interested in?', 
                options=['everything'] + ALL_ATTRACTION_GROUPS, 
                default=['everything'],
                help=attraction_help_text
            )
            
            known_languages_pref = st.multiselect('What other languages do you speak?', options=language_options, help="If you know the local language, the destination will receive a significant bonus in its score.")
            
            with st.expander("Adjust Model Weights"):
                # --- NEW: Preset selection ---
                persona = st.selectbox("Load a preset...", options=list(VACATION_PRESETS.keys()), key='vac_persona')
                weights = VACATION_PRESETS[persona]
                
                w_weather = st.slider("Weight: Weather", 0.0, 1.0, weights['weather'], 0.05, key='w_vac_weather', help="Controls the importance of the weather matching your preference.")
                w_budget = st.slider("Weight: Budget", 0.0, 1.0, weights['budget'], 0.05, key='w_vac_budget', help="Controls the importance of the daily vacation cost matching your budget.")
                w_attr_quantity = st.slider("Weight: Attraction Quantity", 0.0, 1.0, weights['attractions_quantity'], 0.05, key='w_vac_attr_qnt', help="Controls the importance of having a large number of attractions that match your interests.")
                w_attr_quality = st.slider("Weight: Attraction Quality", 0.0, 1.0, weights['attractions_quality'], 0.05, key='w_vac_attr_ql', help="Controls the importance of how highly-rated the attractions of interest are.")
                w_safety = st.slider("Weight: Safety", 0.0, 1.0, weights['safety'], 0.05, key='w_vac_safety', help="Controls the importance of the destination's safety index.")
                w_attr_pop = st.slider('Weight: Popularity', -1.0, 1.0, weights['attractions_popularity'], 0.05, key='w_vac_attr_pop', help="Positive values prefer famous destinations. Negative values prefer less crowded, hidden gems.")
                w_eng_level = st.slider("Weight: English Level", 0.0, 1.0, weights['english_level'], 0.05, key='w_vac_eng', help="Controls the importance of high English proficiency in the destination.")
                w_known_lang = st.slider("Weight: Known Languages", 0.0, 1.0, weights['known_languages'], 0.05, key='w_vac_lang', help="Controls the bonus for destinations where you speak the local language.")
                w_distance = st.slider("Weight: Distance", 0.0, 1.0, weights['distance'], 0.05, key='w_vac_dist', help="Controls the importance of the road distance from Lodz, Poland (closer is better).")
                w_cuisine = st.slider("Weight: Cuisine Quality", 0.0, 1.0, weights['cuisine_quality'], 0.05, key='w_vac_cuisine', help="Controls the importance of the destination's international cuisine ranking.")

        if 'vacation_recs' not in st.session_state:
            st.session_state.vacation_recs = None
        if st.button('Find my perfect vacation!'):
            if not attraction_pref: st.sidebar.error("Please select at least one attraction type (or 'everything').")
            else:
                vacation_preferences = {'month': month_pref,'weather': weather_pref,'budget': budget_pref,'attractions': attraction_pref,'known_languages': known_languages_pref,'excluded_places': final_excluded_list}
                vacation_weights = {'weather': w_weather, 'budget': w_budget, 'attractions_quantity': w_attr_quantity, 'attractions_quality': w_attr_quality, 'safety': w_safety, 'attractions_popularity': w_attr_pop, 'english_level': w_eng_level, 'known_languages': w_known_lang, 'distance': w_distance, 'cuisine_quality': w_cuisine}
                with st.spinner('Thinking...'):
                    recommendations = get_vacation_recommendations(vacation_preferences, vacation_weights)
                    st.session_state.vacation_recs = recommendations
                st.success('Done!')
        if st.session_state.vacation_recs is not None:
            display_recommendations(st.session_state.vacation_recs, main_df)

    elif mode == 'Emigration':
        st.header("Emigration Recommendations")
        with st.sidebar:
            st.subheader("Main Preferences", help="These are the main criteria that will influence the recommendations for long-term living.")
            weather_pref_em = st.selectbox('What climate do you prefer year-round?', options=WEATHER_SCALE, index=4, key='weather_em', help="The model rewards destinations that match this climate for the majority of the year.")
            known_languages_pref_em = st.multiselect('What other languages do you speak?', options=language_options, key='lang_em', help="If you know the local language, the destination will receive a significant bonus in its score.")
            with st.expander("Adjust Model Weights"):
                persona_em = st.selectbox("Load a preset...", options=list(EMIGRATION_PRESETS.keys()), key='em_persona')
                weights_em = EMIGRATION_PRESETS[persona_em]
                w_cost_living = st.slider("Weight: Cost of Living", 0.0, 1.0, weights_em['cost_of_living'], 0.05, key='w_em_cost', help="Importance of low cost of living, including rent.")
                w_purchasing_power = st.slider("Weight: Purchasing Power", 0.0, 1.0, weights_em['purchasing_power'], 0.05, key='w_em_power', help="Importance of high local purchasing power (what you can buy on a local salary).")
                w_safety_em = st.slider("Weight: Safety", 0.0, 1.0, weights_em['safety'], 0.05, key='w_em_safety', help="Importance of a high safety index.")
                w_eng_level_em = st.slider("Weight: English Level", 0.0, 1.0, weights_em['english_level'], 0.05, key='w_em_eng', help="Importance of high English proficiency in the destination.")
                w_hdi = st.slider("Weight: HDI", 0.0, 1.0, weights_em['hdi'], 0.05, key='w_em_hdi', help="Importance of the Human Development Index (overall quality of life).")
                w_unemployment = st.slider("Weight: Unemployment", 0.0, 1.0, weights_em['unemployment'], 0.05, key='w_em_unemp', help="Importance of a low unemployment rate.")
                w_inflation = st.slider("Weight: Inflation", 0.0, 1.0, weights_em['inflation'], 0.05, key='w_em_infl', help="Importance of a low and stable inflation rate.")
                w_life_exp = st.slider("Weight: Life Expectancy", 0.0, 1.0, weights_em['life_expectancy'], 0.05, key='w_em_life', help="Importance of high life expectancy as an indicator of healthcare and quality of life.")
                w_distance_em = st.slider("Weight: Distance", 0.0, 1.0, weights_em['distance'], 0.05, key='w_em_dist', help="Importance of the road distance from Lodz, Poland (closer is better).")
                w_weather_em = st.slider("Weight: Weather", 0.0, 1.0, weights_em['weather'], 0.05, key='w_em_weather', help="Importance of a pleasant year-round climate.")
                w_known_lang_em = st.slider("Weight: Known Languages", 0.0, 1.0, weights_em['known_languages'], 0.05, key='w_em_lang', help="Controls the bonus for destinations where you speak the local language.")
        if 'emigration_recs' not in st.session_state:
            st.session_state.emigration_recs = None
        if st.button('Find the best place to live!'):
            emigration_preferences = {'weather': weather_pref_em, 'known_languages': known_languages_pref_em,'excluded_places': final_excluded_list}
            emigration_weights = {'cost_of_living': w_cost_living, 'purchasing_power': w_purchasing_power, 'safety': w_safety_em, 'english_level': w_eng_level_em, 'hdi': w_hdi, 'unemployment': w_unemployment, 'inflation': w_inflation, 'life_expectancy': w_life_exp, 'distance': w_distance_em,'weather': w_weather_em, 'known_languages': w_known_lang_em}
            with st.spinner('Thinking...'):
                recommendations = get_emigration_recommendations(emigration_preferences, emigration_weights)
                st.session_state.emigration_recs = recommendations
            st.success('Done!')
        if st.session_state.emigration_recs is not None:
            display_recommendations(st.session_state.emigration_recs, main_df)

    # --- Chatbot Interface ---
    st.markdown("---")
    st.header("🤖 Travel Assistant Chatbot")

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Hello! Ask me something about a destination."}]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask about flights, hotels, safety..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.spinner("Thinking..."):
            raw_destination_names = [d.split(' - ')[-1] for d in destination_options]
            response = get_chatbot_response(prompt, main_df, raw_destination_names, country_options, month_options)
            st.session_state.messages.append({"role": "assistant", "content": response})
            with st.chat_message("assistant"):
                st.markdown(response)
else:
    st.error("Could not load the database. Please make sure the 'travel_recommendation_final.db' file is in the same folder as the script.")