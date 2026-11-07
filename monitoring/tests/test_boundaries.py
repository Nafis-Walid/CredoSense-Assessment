from rest_framework import status
from monitoring.constants import (
    SOIL_MOISTURE_LOW_THRESHOLD,
    SOIL_MOISTURE_MIN_VALUE,
    SOIL_MOISTURE_MAX_VALUE,
    TEMPERATURE_MIN_VALUE,
    TEMPERATURE_MAX_VALUE,
)
from .base import BaseTelemetryTestCase


class TelemetryBoundaryTestCase(BaseTelemetryTestCase):
    """
    Data-Driven Conformance Test Suite for Categories A, B, C, and F.
    Uses Python standard library self.subTest() for concise, clean table execution.
    """

    TIMESTAMP_VECTORS = [
        ("TS-01", {"timestamp": "2026-11-06T12:00:00Z"}, status.HTTP_201_CREATED, None),
        ("TS-02", {"timestamp": "2026-11-06T18:00:00+06:00"}, status.HTTP_201_CREATED, None),
        ("TS-03", {"timestamp": "2026-11-06T07:00:00-05:00"}, status.HTTP_201_CREATED, None),
        ("TS-04", {"timestamp": "1970-01-01T00:00:00Z"}, status.HTTP_400_BAD_REQUEST, None),
        ("TS-05", {"timestamp": "1969-12-31T23:59:59Z"}, status.HTTP_400_BAD_REQUEST, None),
        ("TS-06", {"timestamp": "2026-11-06T12:00:00"}, status.HTTP_400_BAD_REQUEST, None),
        ("TS-07", {"timestamp": "not-a-valid-timestamp"}, status.HTTP_400_BAD_REQUEST, None),
    ]

    SOIL_MOISTURE_VECTORS = [
        ("SM-01", {"soil_moisture": SOIL_MOISTURE_MIN_VALUE}, status.HTTP_201_CREATED, ("Low Soil Moisture", True)),
        ("SM-02", {"soil_moisture": SOIL_MOISTURE_MIN_VALUE - 0.1}, status.HTTP_400_BAD_REQUEST, None),
        ("SM-03", {"soil_moisture": -15.0}, status.HTTP_400_BAD_REQUEST, None),
        ("SM-04", {"soil_moisture": SOIL_MOISTURE_MAX_VALUE}, status.HTTP_201_CREATED, ("Low Soil Moisture", False)),
        ("SM-05", {"soil_moisture": SOIL_MOISTURE_MAX_VALUE + 0.1}, status.HTTP_400_BAD_REQUEST, None),
        ("SM-06", {"soil_moisture": 150.0}, status.HTTP_400_BAD_REQUEST, None),
        ("SM-07", {"soil_moisture": SOIL_MOISTURE_LOW_THRESHOLD - 0.1}, status.HTTP_201_CREATED, ("Low Soil Moisture", True)),
        ("SM-08", {"soil_moisture": SOIL_MOISTURE_LOW_THRESHOLD}, status.HTTP_201_CREATED, ("Low Soil Moisture", False)),
    ]

    AIR_TEMPERATURE_VECTORS = [
        ("AT-01", {"air_temperature": TEMPERATURE_MIN_VALUE}, status.HTTP_201_CREATED, None),
        ("AT-02", {"air_temperature": TEMPERATURE_MIN_VALUE - 0.1}, status.HTTP_400_BAD_REQUEST, None),
        ("AT-03", {"air_temperature": -55.0}, status.HTTP_400_BAD_REQUEST, None),
        ("AT-04", {"air_temperature": TEMPERATURE_MAX_VALUE}, status.HTTP_201_CREATED, None),
        ("AT-05", {"air_temperature": TEMPERATURE_MAX_VALUE + 0.1}, status.HTTP_400_BAD_REQUEST, None),
        ("AT-06", {"air_temperature": 95.0}, status.HTTP_400_BAD_REQUEST, None),
    ]

    SCHEMA_CONSTRAINT_VECTORS = [
        ("SC-01", {"device_id": ""}, status.HTTP_400_BAD_REQUEST, None),
        ("SC-02", {"soil_moisture": None}, status.HTTP_400_BAD_REQUEST, None),
        ("SC-03", {"air_temperature": "twenty-five"}, status.HTTP_400_BAD_REQUEST, None),
    ]

    def test_timestamp_and_rtc_boundaries(self):
        """TS-01 to TS-07: Validates UTC, offsets, naive, and epoch rejection."""
        for tid, patch, exp_status, warn in self.TIMESTAMP_VECTORS:
            with self.subTest(vector_id=tid):
                self.execute_vector(tid, patch, exp_status, warn)

    def test_soil_moisture_boundaries(self):
        """SM-01 to SM-08: Validates 0-100% bounds, ADC errors, and <20% alert threshold."""
        for tid, patch, exp_status, warn in self.SOIL_MOISTURE_VECTORS:
            with self.subTest(vector_id=tid):
                self.execute_vector(tid, patch, exp_status, warn)

    def test_air_temperature_envelope(self):
        """AT-01 to AT-06: Validates -40C to +85C operational envelope and extreme exclusions."""
        for tid, patch, exp_status, warn in self.AIR_TEMPERATURE_VECTORS:
            with self.subTest(vector_id=tid):
                self.execute_vector(tid, patch, exp_status, warn)

    def test_schema_field_constraints(self):
        """SC-01 to SC-03: Validates empty IDs, null fields, and non-numeric types."""
        for tid, patch, exp_status, warn in self.SCHEMA_CONSTRAINT_VECTORS:
            with self.subTest(vector_id=tid):
                self.execute_vector(tid, patch, exp_status, warn)
