from django.db import IntegrityError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .constants import (
    DEFAULT_HISTORY_LIMIT,
    HEAT_STRESS_CONSECUTIVE_READINGS,
    HEAT_STRESS_TEMP_DELTA_THRESHOLD,
    MAX_HISTORY_LIMIT,
    SOIL_MOISTURE_LOW_THRESHOLD,
)
from .models import Measurement
from .serializers import MeasurementSerializer


def is_telemetry_identical(record, data):
    """
    Compares telemetry fields with rounding to mitigate IEEE 754 precision drift.
    """
    return (
        round(record.air_temperature, 2) == round(data["air_temperature"], 2)
        and round(record.leaf_temperature, 2) == round(data["leaf_temperature"], 2)
        and round(record.soil_moisture, 2) == round(data["soil_moisture"], 2)
    )


class MeasurementIngestView(APIView):
    """
    API endpoint to accept, validate, and store incoming telemetry.
    Protects against concurrent race conditions and IEEE 754 float drift.
    """

    def post(self, request):
        serializer = MeasurementSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        existing = Measurement.objects.filter(
            device_id=data["device_id"], timestamp=data["timestamp"]
        ).first()

        if existing:
            if is_telemetry_identical(existing, data):
                return Response(MeasurementSerializer(existing).data, status=status.HTTP_200_OK)
            return Response(
                {"detail": "Conflict: Telemetry for this timestamp already recorded with different values."},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except IntegrityError:
            # Handle concurrent race condition: re-fetch winner record and verify identity
            winner = Measurement.objects.filter(
                device_id=data["device_id"], timestamp=data["timestamp"]
            ).first()
            if winner and is_telemetry_identical(winner, data):
                return Response(MeasurementSerializer(winner).data, status=status.HTTP_200_OK)
            return Response(
                {"detail": "Conflict: Telemetry for this timestamp already recorded with different values."},
                status=status.HTTP_409_CONFLICT,
            )


class DeviceHistoryView(APIView):
    """
    API endpoint to retrieve time-series measurement history for a device.
    Uses single-query evaluation and bounded limits to prevent memory exhaustion.
    """

    def get(self, request, device_id):
        try:
            raw_limit = request.query_params.get("limit")
            limit = min(int(raw_limit), MAX_HISTORY_LIMIT) if raw_limit else DEFAULT_HISTORY_LIMIT
            if limit <= 0:
                limit = DEFAULT_HISTORY_LIMIT
        except (ValueError, TypeError):
            limit = DEFAULT_HISTORY_LIMIT

        measurements = list(
            Measurement.objects.filter(device_id=device_id)[:limit]
        )
        if not measurements:
            return Response(
                {"detail": f"No telemetry records found for device '{device_id}'."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = MeasurementSerializer(measurements, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


def evaluate_low_soil_moisture(recent_records):
    """Rule 1: Evaluates low soil moisture on the latest telemetry record."""
    latest = recent_records[0]
    if latest.is_low_soil_moisture:
        return f"Low Soil Moisture: Current soil moisture is {latest.soil_moisture}% (threshold: < {SOIL_MOISTURE_LOW_THRESHOLD}%)."
    return None


def evaluate_heat_stress(recent_records):
    """Rule 2: Evaluates heat stress across required consecutive readings."""
    if (
        len(recent_records) == HEAT_STRESS_CONSECUTIVE_READINGS
        and all(r.satisfies_heat_stress_threshold for r in recent_records)
    ):
        return f"Heat Stress: Leaf temperature exceeded air temperature by >= {HEAT_STRESS_TEMP_DELTA_THRESHOLD}°C in both of the last {HEAT_STRESS_CONSECUTIVE_READINGS} readings."
    return None


# Extensible warning evaluation dispatch table (Strategy Pattern)
WARNING_EVALUATORS = [
    evaluate_low_soil_moisture,
    evaluate_heat_stress,
]


class DeviceStatusView(APIView):
    """
    API endpoint to evaluate device status and trigger agronomic warnings.
    """

    def get(self, request, device_id):
        recent_records = list(
            Measurement.objects.filter(device_id=device_id)[:HEAT_STRESS_CONSECUTIVE_READINGS]
        )
        if not recent_records:
            return Response(
                {"detail": f"No telemetry records found for device '{device_id}'."},
                status=status.HTTP_404_NOT_FOUND,
            )

        latest = recent_records[0]
        warnings = [
            alert
            for evaluate_rule in WARNING_EVALUATORS
            if (alert := evaluate_rule(recent_records)) is not None
        ]

        return Response(
            {
                "device_id": device_id,
                "latest_measurement": MeasurementSerializer(latest).data,
                "warnings": warnings,
            },
            status=status.HTTP_200_OK,
        )
