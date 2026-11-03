from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Measurement(models.Model):
    """
    Environmental telemetry measurement from an agricultural IoT monitoring device.
    """
    device_id = models.CharField(max_length=64, db_index=True)
    timestamp = models.DateTimeField(help_text="Measurement timestamp with timezone")
    air_temperature = models.FloatField(help_text="Air temperature in °C")
    leaf_temperature = models.FloatField(help_text="Leaf temperature in °C")
    soil_moisture = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Soil moisture in percentage (0.0% - 100.0%)"
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
        """Requirement: Soil moisture below 20%."""
        return self.soil_moisture < 20.0

    @property
    def satisfies_heat_stress_threshold(self) -> bool:
        """Requirement threshold: Leaf temp >= air temp + 4.0°C."""
        return self.leaf_temperature >= (self.air_temperature + 4.0)
