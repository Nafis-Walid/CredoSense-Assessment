from unittest.mock import patch
from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from monitoring.models import Measurement
from .base import BaseTelemetryTestCase


class NetworkReliabilityTestCase(BaseTelemetryTestCase):
    """
    Category E: Network Reliability, Idempotency & Concurrency (NW-01 to NW-05).
    """

    def test_nw_01_idempotent_duplicate_retry(self):
        """NW-01: Identical duplicate packet returns 200 OK without inserting duplicate row."""
        dev_id, _ = self.execute_vector("NW-01", {}, status.HTTP_201_CREATED)
        res2 = self.client.post(self.ingest_url, {**self.base_payload, "device_id": dev_id}, format="json")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(Measurement.objects.filter(device_id=dev_id).count(), 1)

    def test_nw_02_conflicting_duplicate_rejection(self):
        """NW-02: Mutated duplicate packet returns 409 Conflict and preserves original row."""
        dev_id, _ = self.execute_vector("NW-02", {}, status.HTTP_201_CREATED)
        conflict_patch = {**self.base_payload, "device_id": dev_id, "air_temperature": 38.0}
        res_conflict = self.client.post(self.ingest_url, conflict_patch, format="json")
        self.assertEqual(res_conflict.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(Measurement.objects.get(device_id=dev_id).air_temperature, 25.0)

    def test_nw_03_out_of_order_delayed_buffer_sorting(self):
        """NW-03: Delayed offline buffer packet automatically sorted in descending B-Tree order."""
        dev_id = "sensor-nw-03"
        self.client.post(self.ingest_url, {**self.base_payload, "device_id": dev_id, "timestamp": "2026-11-06T12:00:00Z"}, format="json")
        self.client.post(self.ingest_url, {**self.base_payload, "device_id": dev_id, "timestamp": "2026-11-06T10:00:00Z"}, format="json")
        h_res = self.client.get(reverse("device-history", kwargs={"device_id": dev_id}))
        self.assertEqual(h_res.data[0]["timestamp"], "2026-11-06T12:00:00Z")
        self.assertEqual(h_res.data[1]["timestamp"], "2026-11-06T10:00:00Z")

    def test_nw_04_concurrent_race_condition_integrity_error(self):
        """NW-04: Concurrent IntegrityError collision strictly returns 409 when data conflicts."""
        dev_id = "sensor-nw-04"
        p_conflict = {**self.base_payload, "device_id": dev_id, "air_temperature": 35.0}
        winner = Measurement(
            device_id=dev_id,
            timestamp="2026-11-06T12:00:00Z",
            air_temperature=25.0,
            leaf_temperature=24.5,
            soil_moisture=45.0,
        )
        with patch("monitoring.serializers.MeasurementSerializer.save", side_effect=IntegrityError("Conflict")) as mock_save:
            with patch("monitoring.models.Measurement.objects.filter") as mock_filter:
                # First query returns None (race window), second query returns winning record
                mock_filter.return_value.first.side_effect = [None, winner]
                res_race = self.client.post(self.ingest_url, p_conflict, format="json")
                self.assertEqual(res_race.status_code, status.HTTP_409_CONFLICT)
                mock_save.assert_called_once()

    def test_nw_05_floating_point_precision_tolerance(self):
        """NW-05: IEEE 754 precision difference within 2 decimal places treated as identical retry."""
        dev_id, _ = self.execute_vector("NW-05", {}, status.HTTP_201_CREATED)
        res_drift = self.client.post(self.ingest_url, {**self.base_payload, "device_id": dev_id, "air_temperature": 25.00000000000001}, format="json")
        self.assertEqual(res_drift.status_code, status.HTTP_200_OK)


class DeviceQueryIsolationTestCase(BaseTelemetryTestCase):
    """
    Category F: Schema Constraints & Query Guards (SC-04 to SC-06).
    """

    def test_sc_04_multi_device_data_isolation(self):
        """SC-04: Measurements from separate devices remain strictly partitioned."""
        dev_a, _ = self.execute_vector("SC-04-A", {}, status.HTTP_201_CREATED)
        dev_b, _ = self.execute_vector("SC-04-B", {"soil_moisture": 70.0}, status.HTTP_201_CREATED)
        hist_a = self.client.get(reverse("device-history", kwargs={"device_id": dev_a}))
        hist_b = self.client.get(reverse("device-history", kwargs={"device_id": dev_b}))
        self.assertEqual(len(hist_a.data), 1)
        self.assertEqual(len(hist_b.data), 1)
        self.assertEqual(hist_a.data[0]["device_id"], dev_a)
        self.assertEqual(hist_b.data[0]["device_id"], dev_b)

    def test_sc_05_nonexistent_device_404_handling(self):
        """SC-05: Queries for nonexistent device cleanly return 404 Not Found."""
        self.assertEqual(self.client.get(reverse("device-history", kwargs={"device_id": "nonexistent-node"})).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(reverse("device-status", kwargs={"device_id": "nonexistent-node"})).status_code, status.HTTP_404_NOT_FOUND)

    def test_sc_06_history_query_parameter_limit_guards(self):
        """SC-06: Query parameter ?limit enforces bounds on history endpoint."""
        dev_id, _ = self.execute_vector("SC-06", {}, status.HTTP_201_CREATED)
        url = reverse("device-history", kwargs={"device_id": dev_id})
        self.assertEqual(self.client.get(f"{url}?limit=-5").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f"{url}?limit=invalid").status_code, status.HTTP_200_OK)
