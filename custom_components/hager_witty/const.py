from __future__ import annotations

DOMAIN = "hager_witty"
NAME = "Hager Witty Start"

DISCOVERY_URL = "https://login.hager.com/.well-known/openid-configuration"
CLIENT_ID = "4thnuynw5c2bq9kdpqxhaz43n3psw7fx"
REDIRECT_URI = "com.miaaguardusercontent.tenants.hag7ad4d0s9j7q.prd:/callback"
SCOPE = "openid profile email iot topaze installation:energy:read installation:energy:write"
AUDIENCE = "mph-homeautomation"
API_BASE = "https://api-hsiot.hager-iot.com/private/"
APIM_SUBSCRIPTION_KEY = "8cbdd7aeea8146b98aff541ff0cff049"

CONF_COUNTRY = "country"
CONF_LOCALE = "locale"
CONF_AUTH_CODE = "authorization_code"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_EXPIRES_AT = "expires_at"
CONF_TOKEN_ENDPOINT = "token_endpoint"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "device_name"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_COUNTRY = "FR"
DEFAULT_LOCALE = "fr"
DEFAULT_SCAN_INTERVAL = 10
MIN_SCAN_INTERVAL = 2
MAX_SCAN_INTERVAL = 300

# StatusEvent.Type values observed and validated against the real charger.
EVENT_CHARGER_AVAILABLE = 2006
EVENT_VEHICLE_AVAILABLE = 2007
EVENT_VEHICLE_CHARGING = 2009
KNOWN_EVENT_TYPES = {
    EVENT_CHARGER_AVAILABLE,
    EVENT_VEHICLE_AVAILABLE,
    EVENT_VEHICLE_CHARGING,
}

PLATFORMS = ["sensor", "binary_sensor", "switch"]
