import os
import requests
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)

# OWM_API_KEY loaded from environment variables
API_KEY = os.environ.get("OWM_API_KEY")

CATEGORY_RULES = {
    "cold_beverages": {
        "temp_threshold": 38,
        "per_degree_pct": 4,
        "rain_penalty_pct": -20,
    },
    "dairy_chaas_lassi": {
        "temp_threshold": 36,
        "per_degree_pct": 5,
        "rain_penalty_pct": -10,
    },
    "hot_snacks": {
        "temp_threshold": 34,
        "per_degree_pct": -3,
        "rain_penalty_pct": 15,
    },
    "general_staples": {
        "temp_threshold": None,
        "per_degree_pct": 0,
        "rain_penalty_pct": -25,
    },
}

ENTERPRISE_CONFIGS = {
    "standard_vendor": {"buffer_pct": 0, "range_spread": 10},
    "retail_chain": {
        "buffer_pct": 5,
        "range_spread": 5,
    },
}


def get_forecast(city):
    """Fetches weather forecast with error handling for API failures."""
    if not API_KEY:
        raise RuntimeError("OWM_API_KEY environment variable is not set.")

    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"q": city, "appid": API_KEY, "units": "metric"}

    try:
        response = requests.get(url, params=params, timeout=10)

        # Explicit handling for 404 City Not Found
        if response.status_code == 404:
            raise ValueError(f"City '{city}' was not found.")

        response.raise_for_status()
        data = response.json()

        if "list" not in data or not data["list"]:
            raise ValueError(f"Could not retrieve forecast list for city: '{city}'.")

        first = data["list"][0]
        temp = float(first["main"]["temp"])

        # Safe extraction of probability of precipitation ('pop')
        raw_pop = first.get("pop")
        rain_prob = float(raw_pop) * 100 if raw_pop is not None else 0.0

        return temp, rain_prob

    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Failed to connect to OpenWeatherMap API: {e}")


def recommend(category, baseline_units, temp, rain_prob, tier="standard_vendor"):
    """Calculates the adjusted inventory recommendation range."""
    rule = CATEGORY_RULES.get(category, CATEGORY_RULES["general_staples"])
    config = ENTERPRISE_CONFIGS.get(tier, ENTERPRISE_CONFIGS["standard_vendor"])

    adj = 0
    if rule["temp_threshold"] and temp > rule["temp_threshold"]:
        adj += (temp - rule["temp_threshold"]) * rule["per_degree_pct"]
    if rain_prob > 50:
        adj += rule["rain_penalty_pct"]  # ty:ignore[unsupported-operator]

    # Apply safety buffer for enterprise orders
    adjusted_baseline = baseline_units * (1 + (config["buffer_pct"] / 100))

    spread = config["range_spread"]
    low_calc = max(0, round(adjusted_baseline * (1 + (adj - spread) / 100)))
    high_calc = max(0, round(adjusted_baseline * (1 + (adj + spread) / 100)))

    return min(low_calc, high_calc), max(low_calc, high_calc)


@app.route("/")
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Weather-Based Inventory API</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; background-color: #f4f4f9; color: #333; }
            code { background: #e2e8f0; padding: 2px 6px; border-radius: 4px; }
            .container { max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Weather-Based Inventory API</h2>
            <p>The application is running successfully.</p>
            <p>Example Endpoint Usage:</p>
            <p><code>/api/recommend?city=Ahmedabad&category=cold_beverages&baseline=50</code></p>
        </div>
    </body>
    </html>
    """
    return render_template_string(html_content)


@app.route("/api/recommend", methods=["GET"])
def api_recommend():
    try:
        city = request.args.get("city", "Ahmedabad").strip()
        category = request.args.get("category", "cold_beverages").strip()
        tier = request.args.get("tier", "standard_vendor").strip()

        # Input Validations
        if category not in CATEGORY_RULES:
            return jsonify({"error": f"Invalid category '{category}'. Valid categories: {list(CATEGORY_RULES.keys())}"}), 400

        if tier not in ENTERPRISE_CONFIGS:
            return jsonify({"error": f"Invalid tier '{tier}'. Valid tiers: {list(ENTERPRISE_CONFIGS.keys())}"}), 400

        try:
            baseline_raw = request.args.get("baseline", 50)
            baseline = float(baseline_raw)
            if baseline < 0:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"error": "Baseline units must be a valid non-negative number."}), 400

        temp, rain_prob = get_forecast(city)
        low, high = recommend(category, baseline, temp, rain_prob, tier=tier)

        return jsonify({
            "city": city,
            "category": category,
            "tier": tier,
            "temp": temp,
            "rain_prob": rain_prob,
            "suggested_range": [low, high],
        }), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except ConnectionError as e:
        return jsonify({"error": str(e)}), 502
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=81, debug=False)