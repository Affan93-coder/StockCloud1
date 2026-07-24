import logging
import os
from flask import Flask, jsonify, render_template, request
import requests
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

# -----------------------------------
# Logging Configuration
# -----------------------------------
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# -----------------------------------
# App Setup & Environment Variables
# -----------------------------------
app = Flask(__name__)

OWM_API_KEY = os.getenv("OWM_API_KEY")
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# -----------------------------------
# Safe Twilio Initialization
# -----------------------------------
twilio_client = None

if TWILIO_SID and TWILIO_TOKEN:
  try:
    twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)
    logger.info("Twilio client initialized successfully.")
  except Exception as e:
    logger.error("Failed to initialize Twilio client: %s", e)
else:
  logger.warning(
      "Twilio credentials not fully provided. SMS functionality will be"
      " disabled."
  )

# -----------------------------------
# Business Rules Configuration
# -----------------------------------
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


# -----------------------------------
# Helper Services
# -----------------------------------
def send_alert(to_number: str, message: str):
  """Sends an SMS using Twilio safely.

  Parameters
  ----------
  to_number : str
      Recipient phone number in E.164 format (e.g., +919876543210).
  message : str
      SMS message body.

  Returns
  -------
  MessageInstance | None
  """
  if twilio_client is None:
    logger.error("SMS trigger failed: Twilio client is not initialized.")
    return None

  if not TWILIO_FROM_NUMBER:
    logger.error(
        "SMS trigger failed: TWILIO_PHONE_NUMBER environment variable is"
        " missing."
    )
    return None

  if not to_number or not isinstance(to_number, str):
    logger.error(
        "SMS trigger failed: Recipient phone number must be a valid string."
    )
    return None

  if not message or not isinstance(message, str):
    logger.error("SMS trigger failed: Message body cannot be empty.")
    return None

  try:
    sms = twilio_client.messages.create(
        body=message.strip(),
        from_=TWILIO_FROM_NUMBER,
        to=to_number.strip(),
    )
    logger.info("SMS sent successfully to %s. SID: %s", to_number, sms.sid)
    return sms

  except TwilioRestException as e:
    logger.error("Twilio API Error while sending to %s: %s", to_number, e)
    return None
  except Exception as e:
    logger.exception("Unexpected error while sending SMS: %s", e)
    return None


def get_forecast(city: str):
  """Fetches weather forecast with complete error handling for OWM API."""
  if not OWM_API_KEY:
    raise RuntimeError("OWM_API_KEY environment variable is not set.")

  url = "https://api.openweathermap.org/data/2.5/forecast"
  params = {"q": city, "appid": OWM_API_KEY, "units": "metric"}

  try:
    response = requests.get(url, params=params, timeout=10)

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


def recommend(
    category: str,
    baseline_units: float,
    temp: float,
    rain_prob: float,
    tier="standard_vendor",
):
  """Calculates the adjusted inventory recommendation range safely."""
  rule = CATEGORY_RULES.get(category, CATEGORY_RULES["general_staples"])
  config = ENTERPRISE_CONFIGS.get(tier, ENTERPRISE_CONFIGS["standard_vendor"])

  adj = 0.0
  if rule["temp_threshold"] is not None and temp > rule["temp_threshold"]:
    adj += (temp - rule["temp_threshold"]) * rule["per_degree_pct"]  # ty:ignore[unsupported-operator]

  if rain_prob > 50:
    adj += rule["rain_penalty_pct"]  # ty:ignore[unsupported-operator]

  # Safety buffer calculation
  adjusted_baseline = baseline_units * (1 + (config["buffer_pct"] / 100))

  spread = config["range_spread"]
  low_calc = max(0, round(adjusted_baseline * (1 + (adj - spread) / 100)))
  high_calc = max(0, round(adjusted_baseline * (1 + (adj + spread) / 100)))

  return min(low_calc, high_calc), max(low_calc, high_calc)


# -----------------------------------
# Web & API Endpoints
# -----------------------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/recommend", methods=["GET"])
def api_recommend():
  try:
    city = request.args.get("city", "Ahmedabad").strip()
    category = request.args.get("category", "cold_beverages").strip()
    tier = request.args.get("tier", "standard_vendor").strip()

    should_send_sms = request.args.get("send_sms", "false").lower() in [
        "true",
        "1",
        "yes",
    ]
    to_phone = request.args.get("phone", "").strip()

    # Validations
    if category not in CATEGORY_RULES:
      return (
          jsonify({
              "error": (
                  f"Invalid category '{category}'. Valid categories:"
                  f" {list(CATEGORY_RULES.keys())}"
              )
          }),
          400,
      )

    if tier not in ENTERPRISE_CONFIGS:
      return (
          jsonify({
              "error": (
                  f"Invalid tier '{tier}'. Valid tiers:"
                  f" {list(ENTERPRISE_CONFIGS.keys())}"
              )
          }),
          400,
      )

    try:
      baseline_raw = request.args.get("baseline", 50)
      baseline = float(baseline_raw)
      if baseline < 0:
        raise ValueError
    except (ValueError, TypeError):
      return (
          jsonify(
              {"error": "Baseline units must be a valid non-negative number."}
          ),
          400,
      )

    # Processing logic
    temp, rain_prob = get_forecast(city)
    low, high = recommend(category, baseline, temp, rain_prob, tier=tier)

    response_payload = {
        "city": city,
        "category": category,
        "tier": tier,
        "temp": temp,
        "rain_prob": rain_prob,
        "suggested_range": [low, high],
        "sms_sent": False,
    }

    # Handle SMS trigger if explicitly requested
    if should_send_sms:
      if not to_phone:
        return (
            jsonify({
                "error": (
                    "A valid 'phone' parameter in E.164 format (e.g."
                    " +919876543210) is required when send_sms=true."
                )
            }),
            400,
        )

      sms_text = (
          f"Inventory Alert for {city}: Suggested range for {category} is"
          f" {low}-{high} units. (Temp: {temp}°C, Rain: {rain_prob}%)."
      )
      sms_result = send_alert(to_phone, sms_text)

      response_payload["sms_sent"] = bool(sms_result)
      if sms_result:
        response_payload["sms_sid"] = sms_result.sid

    return jsonify(response_payload), 200

  except ValueError as e:
    return jsonify({"error": str(e)}), 400
  except ConnectionError as e:
    return jsonify({"error": str(e)}), 502
  except RuntimeError as e:
    return jsonify({"error": str(e)}), 500
  except Exception as e:
    logger.exception("Unexpected error in /api/recommend: %s", e)
    return (
        jsonify({"error": f"An unexpected server error occurred: {str(e)}"}),
        500,
    )


@app.route("/api/send-alert", methods=["POST"])
def manual_send_alert():
  """Dedicated endpoint to dispatch custom alerts via POST payload."""
  data = request.get_json(silent=True) or {}
  to_number = data.get("phone")
  message = data.get("message")

  if not to_number or not message:
    return (
        jsonify(
            {"error": "Both 'phone' and 'message' JSON fields are required."}
        ),
        400,
    )

  sms_instance = send_alert(to_number, message)
  if sms_instance:
    return jsonify({"status": "success", "sms_sid": sms_instance.sid}), 200
  else:
    return (
        jsonify({
            "error": "Failed to send SMS alert. Check server logs for details."
        }),
        500,
    )


# -----------------------------------
# Server Execution (Render Dynamic Port Fix)
# -----------------------------------
if __name__ == "__main__":
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port, debug=False)