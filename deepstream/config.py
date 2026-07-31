"""Central configuration for the Deepstream signal engine.

All thresholds, asset definitions, and risk parameters live here so the
behaviour of the platform is auditable and configurable without touching
the analysis code.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PARAM_FILE = BASE_DIR / "optimized_parameters.json"
SIGNAL_FILE = BASE_DIR / "latest_signal.json"
TRACK_RECORD_FILE = BASE_DIR / "track_record.json"
SITE_SIGNAL_FILE = BASE_DIR / "signal_site" / "latest_signal.json"
SITE_TRACK_FILE = BASE_DIR / "signal_site" / "track_record.json"
SITE_CHART_FILE = BASE_DIR / "signal_site" / "chart_data.json"
LOG_FILE = BASE_DIR / "deepstream.log"

# ---------------------------------------------------------------------------
# Asset pairs monitored by the platform
# ---------------------------------------------------------------------------
PAIRS = {
    1: {
        "id": 1,
        "name": "Pacific SST / Copper",
        "pair": "ENSO — Pacific Sea Surface Temperature → Copper Futures",
        "ocean_file": "noaa_sst_processed.csv",
        "price_file": "HG_F_processed.csv",
        "ocean_col": "SST_Anomaly",
        "price_col": "HG_F_Price",
        "monthly_ocean": True,
        "narrative": (
            "El Niño / La Niña cycles alter rainfall around South American "
            "copper mines, disrupting production and pushing prices."
        ),
    },
    2: {
        "id": 2,
        "name": "Atlantic Chlorophyll / Tuna",
        "pair": "Atlantic Chlorophyll → Tuna Price",
        "ocean_file": "chlorophyll_processed.csv",
        "price_file": "tuna_processed.csv",
        "ocean_col": "Chlorophyll",
        "price_col": "Tuna_Price",
        "monthly_ocean": False,
        "narrative": (
            "Chlorophyll collapses signal nutrient disruption in the food "
            "chain, constraining catch yields and raising tuna prices."
        ),
    },
    3: {
        "id": 3,
        "name": "GoM Chemical Plume / Crude Oil",
        "pair": "Gulf of Mexico Chemical Plume → Crude Oil Futures",
        "ocean_file": "chemical_plume_processed.csv",
        "price_file": "CL_F_processed.csv",
        "ocean_col": "Chemical_Plume",
        "price_col": "CL_F_Price",
        "monthly_ocean": False,
        "narrative": (
            "Subsea chemical plumes indicate infrastructure leakage; "
            "tradeable as discrete event catalysts rather than a continuous signal."
        ),
    },
}

# ---------------------------------------------------------------------------
# Confidence thresholds (absolute Pearson correlation)
# ---------------------------------------------------------------------------
CONFIDENCE_THRESHOLDS = {
    "HIGH": 0.70,
    "MEDIUM": 0.40,
    "LOW": 0.20,
}

# Only signals at or above this confidence are emitted as tradeable.
MIN_TRADE_CONFIDENCE = "MEDIUM"

# ---------------------------------------------------------------------------
# Risk parameters for trade setup generation
# ---------------------------------------------------------------------------
STOP_LOSS_PCT = 0.05    # 5% stop from entry
TAKE_PROFIT_PCT = 0.08  # 8% take profit from entry
CHANGE_WINDOW_MAX = 30  # days used to measure the ocean signal move
PRICE_WINDOW_MAX = 30   # days used to measure the recent price move

# ---------------------------------------------------------------------------
# Walk-forward track record settings
# ---------------------------------------------------------------------------
TRACK_HOLDING_DAYS = 60       # max days a simulated trade is held
TRACK_STEP_DAYS = 7           # evaluate a new entry every N days
TRACK_MIN_SAMPLES = 20        # minimum observations before publishing a stat
TRACK_LOOKBACK_DAYS = 365 * 5 # use the last 5 years of data for the record

# ---------------------------------------------------------------------------
# Delivery / Telegram
# ---------------------------------------------------------------------------
TELEGRAM_TOKEN_ENV = "DEEPSTREAM_BOT_TOKEN"
TELEGRAM_CHANNEL_ENV = "DEEPSTREAM_CHANNEL_ID"

# Private Telegram channel reserved for Pro subscribers. The bot must be an
# admin there so it can mint single-use invite links after a paid checkout.
PRO_CHANNEL_ENV = "DEEPSTREAM_PRO_CHANNEL_ID"

# ---------------------------------------------------------------------------
# Payments (Cashfree — Payment Gateway)
# ---------------------------------------------------------------------------
CASHFREE_CLIENT_ID_ENV = "CASHFREE_CLIENT_ID"          # public client id (dashboard -> API keys)
CASHFREE_CLIENT_SECRET_ENV = "CASHFREE_CLIENT_SECRET"  # secret key — server-side only
CASHFREE_ENV_ENV = "CASHFREE_ENV"                      # "sandbox" (default) or "production"
CASHFREE_API_VERSION_ENV = "CASHFREE_API_VERSION"      # e.g. 2023-08-01
CASHFREE_WEBHOOK_SECRET_ENV = "CASHFREE_WEBHOOK_SECRET"  # verifies webhook signatures
CASHFREE_ORDER_AMOUNT_ENV = "CASHFREE_ORDER_AMOUNT"    # USD charged per Pro month
CASHFREE_ORDER_CURRENCY_ENV = "CASHFREE_ORDER_CURRENCY"  # e.g. USD
CASHFREE_SITE_URL_ENV = "CASHFREE_SITE_URL"            # base URL of the landing site

# Subscription state cache (lean cache of access decisions).
SUBSCRIPTIONS_FILE = BASE_DIR / "data" / "subscriptions.json"

# Server routes for the payment flow.
CASHFREE_WEBHOOK_PATH = "/webhooks/cashfree"
ACCESS_API_PATH = "/api/access"
CREATE_ORDER_API_PATH = "/api/create-order"
PAYMENTS_CONFIG_API_PATH = "/api/payments_config"
