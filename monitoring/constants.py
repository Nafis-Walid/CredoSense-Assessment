import os

# Low soil moisture threshold (default: 20.0%)
SOIL_MOISTURE_LOW_THRESHOLD = float(os.getenv("SOIL_MOISTURE_LOW_THRESHOLD", 20.0))

# Heat stress leaf-to-air delta threshold (default: 4.0°C)
HEAT_STRESS_TEMP_DELTA_THRESHOLD = float(os.getenv("HEAT_STRESS_TEMP_DELTA_THRESHOLD", 4.0))

# Heat stress consecutive readings count (default: 2)
HEAT_STRESS_CONSECUTIVE_READINGS = int(os.getenv("HEAT_STRESS_CONSECUTIVE_READINGS", 2))

# Hardware clock drift tolerance window (minutes)
CLOCK_DRIFT_TOLERANCE_MINUTES = int(os.getenv("CLOCK_DRIFT_TOLERANCE_MINUTES", 1))

# Physical soil moisture percentage bounds
SOIL_MOISTURE_MIN_VALUE = 0.0
SOIL_MOISTURE_MAX_VALUE = 100.0

# Physical sensor temperature bounds (°C) (e.g. Sensirion SHT series)
TEMPERATURE_MIN_VALUE = float(os.getenv("TEMPERATURE_MIN_VALUE", -40.0))
TEMPERATURE_MAX_VALUE = float(os.getenv("TEMPERATURE_MAX_VALUE", 85.0))

# Default and maximum history record limit per query
DEFAULT_HISTORY_LIMIT = int(os.getenv("DEFAULT_HISTORY_LIMIT", 100))
MAX_HISTORY_LIMIT = int(os.getenv("MAX_HISTORY_LIMIT", 1000))

