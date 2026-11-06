from django.urls import path
from .views import DeviceHistoryView, DeviceStatusView, MeasurementIngestView

urlpatterns = [
    path("measurements/", MeasurementIngestView.as_view(), name="measurement-ingest"),
    path("devices/<str:device_id>/history/", DeviceHistoryView.as_view(), name="device-history"),
    path("devices/<str:device_id>/status/", DeviceStatusView.as_view(), name="device-status"),
]
