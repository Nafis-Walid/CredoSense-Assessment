from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class BaseTelemetryTestCase(APITestCase):
    """
    Base test fixture providing canonical baseline telemetry payload
    and a unified mutation driver for edge and boundary testing.
    """

    def setUp(self):
        self.ingest_url = reverse("measurement-ingest")
        self.base_payload = {
            "device_id": "sensor-alpha-01",
            "timestamp": "2026-11-06T12:00:00Z",
            "air_temperature": 25.0,
            "leaf_temperature": 24.5,
            "soil_moisture": 45.0,
        }

    def execute_vector(self, test_id, patch, expected_status, warning_check=None):
        """Unified driver: clones baseline payload, mutates fields, posts telemetry, and checks status & warnings."""
        payload = {**self.base_payload, "device_id": f"sensor-{test_id.lower()}"}
        for key, val in patch.items():
            if val is None:
                payload.pop(key, None)
            else:
                payload[key] = val
        res = self.client.post(self.ingest_url, payload, format="json")
        self.assertEqual(res.status_code, expected_status)

        if warning_check:
            keyword, should_exist = warning_check
            s_res = self.client.get(reverse("device-status", kwargs={"device_id": payload["device_id"]}))
            self.assertEqual(s_res.status_code, status.HTTP_200_OK)
            has_warning = any(keyword in w for w in s_res.data["warnings"])
            self.assertEqual(has_warning, should_exist)

        return payload["device_id"], res
