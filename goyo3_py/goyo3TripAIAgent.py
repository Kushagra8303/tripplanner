from fastapi import FastAPI
import requests
import os
import json
from openai import OpenAI

app = FastAPI(title="Free Trip Planner")

# Use OpenAI API key from environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # ✅ no hardcoded key
client = OpenAI(api_key=OPENAI_API_KEY)

# Hobby -> Overpass tags
HOBBY_MAP = {
    "culture": ['tourism=museum', 'historic=yes'],
    "adventure": ['leisure=park', 'sport=*'],
    "food": ['amenity=restaurant'],
    "shopping": ['shop=*']
}

# Fetch POIs from Overpass
def fetch_pois_osm(city: str, hobby: str, limit=10):
    tags = HOBBY_MAP.get(hobby.lower(), ['tourism=museum'])
    pois = []

    for tag in tags:
        key_value = tag.split('=')
        key, value = key_value[0], key_value[1]

        query = f"""
        [out:json][timeout:25];
        area["name"="{city}"]->.searchArea;
        node["{key}"="{value}"](area.searchArea);
        out center;
        """

        url = "https://overpass-api.de/api/interpreter"
        try:
            response = requests.post(url, data={"data": query}, timeout=30)
            data = response.json()
            for el in data.get("elements", [])[:limit]:
                pois.append({
                    "name": el.get("tags", {}).get("name", "Unknown"),
                    "lat": el.get("lat"),
                    "lon": el.get("lon"),
                    "category": hobby
                })
        except Exception as e:
            print("OSM fetch error:", e)
            continue

    return pois[:limit]

# Generate itinerary using GPT
def generate_itinerary(city, budget, duration, hobby, pois):
    pois_text = "\n".join([f"{p['name']} ({p['category']})" for p in pois])
    prompt = f"""
You are a travel planner AI.
City: {city}
Duration: {duration} days
Budget: {budget} INR
Hobby: {hobby}

POIs:
{pois_text}

Tasks:
1. Plan a day-wise itinerary.
2. Suggest budget-friendly stay & food options.
3. Suggest shopping/market options.
4. Add a section 'avoid_expenses' for unnecessary costs.
5. Return JSON strictly like this:
{{
  "city": "...",
  "budget": ...,
  "duration_days": ...,
  "hobby": "...",
  "plan": {{"day_1": {{"places_to_visit": [...], "stay": "...", "food": "...", "shopping": "..."}}}},
  "total_cost": ...,
  "within_budget": true/false,
  "avoid_expenses": ["...", "..."]
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a professional trip planner AI."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    itinerary_str = response.choices[0].message.content
    try:
        itinerary_json = json.loads(itinerary_str)
    except:
        itinerary_json = {"error": "AI returned invalid JSON", "raw": itinerary_str}

    return itinerary_json

# API endpoint
@app.get("/plan_trip")
def plan_trip(city: str, budget: int, duration: int, hobby: str):
    pois = fetch_pois_osm(city, hobby, limit=15)
    if not pois:
        return {"error": "No POIs found for this city/hobby"}
    itinerary = generate_itinerary(city, budget, duration, hobby, pois)
    return {"plan": itinerary, "pois": pois[:5]}








