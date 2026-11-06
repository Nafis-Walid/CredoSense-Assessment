import re
from rest_framework import serializers
from django.utils import timezone
from .constants import (
    CLOCK_DRIFT_TOLERANCE_MINUTES,
    TEMPERATURE_MIN_VALUE,
    TEMPERATURE_MAX_VALUE,
)
from .models import Measurement


class MeasurementSerializer(serializers.ModelSerializer):
    """
    Serializer for validating and transforming incoming environmental telemetry.
    Inherits field constraints (e.g. soil moisture range) directly from Measurement model.
    """
    class Meta:
        model = Measurement
        fields = [
            'id',
            'device_id',
            'timestamp',
            'air_temperature',
            'leaf_temperature',
            'soil_moisture',
            'received_at',
        ]
        read_only_fields = ['id', 'received_at']
        validators = []  # Bypass auto unique constraint validation to handle idempotency in view

    def validate_timestamp(self, value):
        """
        Enforce strict ISO 8601 / RFC 3339 timezone awareness, uninitialized RTC clock rejection,
        and realistic future tolerance for hardware clock skew.
        """
        raw_ts = str(self.initial_data.get('timestamp', '')).strip()
        if not re.search(r'(Z|[+-]\d{2}:?\d{2})$', raw_ts):
            raise serializers.ValidationError(
                "Measurement timestamp must explicitly include timezone information (e.g. '2026-11-04T01:00:00Z' or '+06:00')."
            )

        if value.timestamp() <= 0:
            raise serializers.ValidationError(
                "Timestamp indicates an uninitialized hardware clock (Epoch 1970)."
            )

        now_with_drift = timezone.now() + timezone.timedelta(minutes=CLOCK_DRIFT_TOLERANCE_MINUTES)
        if value > now_with_drift:
            raise serializers.ValidationError(
                f"Timestamp cannot be in the future (exceeds {CLOCK_DRIFT_TOLERANCE_MINUTES}-minute clock drift margin)."
            )

        return value

    def validate_air_temperature(self, value):
        """Reject unphysical air temperature readings outside operating range."""
        if not (TEMPERATURE_MIN_VALUE <= value <= TEMPERATURE_MAX_VALUE):
            raise serializers.ValidationError(
                f"Air temperature {value}°C is outside valid sensor range ({TEMPERATURE_MIN_VALUE}°C to {TEMPERATURE_MAX_VALUE}°C)."
            )
        return value

    def validate_leaf_temperature(self, value):
        """Reject unphysical leaf temperature readings outside operating range."""
        if not (TEMPERATURE_MIN_VALUE <= value <= TEMPERATURE_MAX_VALUE):
            raise serializers.ValidationError(
                f"Leaf temperature {value}°C is outside valid sensor range ({TEMPERATURE_MIN_VALUE}°C to {TEMPERATURE_MAX_VALUE}°C)."
            )
        return value
