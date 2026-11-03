from rest_framework import serializers
from django.utils import timezone
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

    def validate_timestamp(self, value):
        """
        Requirement: Enforce that the timestamp explicitly includes timezone info.
        """
        if timezone.is_naive(value):
            raise serializers.ValidationError(
                "Measurement timestamp must include timezone information (e.g. '2026-11-03T10:00:00Z' or '+06:00')."
            )
        return value
