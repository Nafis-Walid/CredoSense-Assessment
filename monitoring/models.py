from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from .constants import (
    HEAT_STRESS_TEMP_DELTA_THRESHOLD,
    SOIL_MOISTURE_LOW_THRESHOLD,
    SOIL_MOISTURE_MAX_VALUE,
    SOIL_MOISTURE_MIN_VALUE,
)


class Measurement(models.Model):
    """
    Environmental telemetry measurement from an agricultural IoT monitoring device.
    """
    device_id = models.CharField(max_length=64, db_index=True)
    timestamp = models.DateTimeField(help_text="Measurement timestamp with timezone")
    air_temperature = models.FloatField(help_text="Air temperature in °C")
    leaf_temperature = models.FloatField(help_text="Leaf temperature in °C")
    soil_moisture = models.FloatField(
        validators=[
            MinValueValidator(SOIL_MOISTURE_MIN_VALUE),
            MaxValueValidator(SOIL_MOISTURE_MAX_VALUE),
        ],
        help_text=f"Soil moisture percentage ({SOIL_MOISTURE_MIN_VALUE}% - {SOIL_MOISTURE_MAX_VALUE}%)"
    )
    received_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Server-side ingestion timestamp for latency auditing"
    )

    class Meta:
        ordering = ['-timestamp']
        constraints = [
            models.UniqueConstraint(
                fields=['device_id', 'timestamp'],
                name='unique_device_timestamp_reading'
            )
        ]
        indexes = [
            models.Index(fields=['device_id', '-timestamp'], name='idx_device_timestamp_desc'),
        ]

    def __str__(self):
        return f"[{self.device_id}] @ {self.timestamp}"

    @property
    def is_low_soil_moisture(self) -> bool:
        """Dynamic check against low soil moisture threshold."""
        return self.soil_moisture < SOIL_MOISTURE_LOW_THRESHOLD

    @property
    def satisfies_heat_stress_threshold(self) -> bool:
        """Dynamic check against heat stress temperature delta threshold."""
        return self.leaf_temperature >= (self.air_temperature + HEAT_STRESS_TEMP_DELTA_THRESHOLD)
