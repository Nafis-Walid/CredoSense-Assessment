from django.urls import reverse
from .base import BaseTelemetryTestCase


class HeatStressAlertTestCase(BaseTelemetryTestCase):
    """
    Category D: Leaf Temperature & Heat Stress Differential Tests (HS-01 to HS-04).
    Validates consecutive reading requirements and multi-warning states.
    """

    HEAT_STRESS_VECTORS = [
        ("HS-01", [(25.0, 29.0, 45.0)], False, False),
        ("HS-02", [(25.0, 29.0, 45.0), (26.0, 30.5, 45.0)], True, False),
        ("HS-03", [(25.0, 29.0, 45.0), (25.0, 28.9, 45.0)], False, False),
        ("HS-04", [(25.0, 29.5, 15.0), (26.0, 30.5, 14.0)], True, True),
    ]

    def test_heat_stress_sequences(self):
        """HS-01 to HS-04: Validates consecutive streak requirements and multi-warning states."""
        for tid, readings, exp_heat, exp_moist in self.HEAT_STRESS_VECTORS:
            with self.subTest(vector_id=tid):
                dev_id = f"sensor-hs-{tid.lower()}"
                for idx, (air, leaf, soil) in enumerate(readings):
                    self.client.post(
                        self.ingest_url,
                        {
                            **self.base_payload,
                            "device_id": dev_id,
                            "timestamp": f"2026-11-06T12:0{idx}:00Z",
                            "air_temperature": air,
                            "leaf_temperature": leaf,
                            "soil_moisture": soil,
                        },
                        format="json",
                    )
                s_res = self.client.get(reverse("device-status", kwargs={"device_id": dev_id}))
                self.assertEqual(any("Heat Stress" in w for w in s_res.data["warnings"]), exp_heat)
                self.assertEqual(any("Low Soil Moisture" in w for w in s_res.data["warnings"]), exp_moist)
