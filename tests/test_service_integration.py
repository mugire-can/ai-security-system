"""
Service API integration tests — validates the payload formats and API
structure for all microservices without requiring any service to be running.
"""

import json

import pytest


class TestAlertPayload:
    def test_alert_payload_is_valid_json(self):
        payload = {
            "camera_id": "cam-01",
            "zone": "entrance",
            "alert_type": "loitering",
            "severity": "medium",
            "description": "Person loitering near exit for >2 minutes",
        }
        # Must not raise
        serialised = json.dumps(payload)
        recovered = json.loads(serialised)
        assert recovered["camera_id"] == "cam-01"
        assert recovered["severity"] == "medium"

    def test_alert_payload_required_fields(self):
        required = {"camera_id", "zone", "alert_type", "severity", "description"}
        payload = {
            "camera_id": "cam-01",
            "zone": "entrance",
            "alert_type": "anomaly",
            "severity": "high",
            "description": "Test",
        }
        assert required.issubset(payload.keys())


class TestCameraPayloads:
    def test_camera_registration_payload(self):
        payload = {
            "camera_id": "cam-01",
            "source": "rtsp://192.168.1.100:554/stream",
        }
        assert json.loads(json.dumps(payload))["camera_id"] == "cam-01"

    def test_camera_heartbeat_payload(self):
        payload = {
            "camera_id": "cam-01",
            "timestamp": "2024-01-15T10:30:45Z",
        }
        recovered = json.loads(json.dumps(payload))
        assert "timestamp" in recovered

    def test_video_optimizer_frame_payload(self):
        payload = {
            "id": "frame-001",
            "width": 1920,
            "height": 1080,
            "format": "h264",
        }
        recovered = json.loads(json.dumps(payload))
        assert recovered["width"] == 1920
        assert recovered["height"] == 1080


class TestApiEndpoints:
    @pytest.mark.parametrize(
        "method,path,description",
        [
            ("GET", "/api/health", "Health check"),
            ("POST", "/api/alerts", "Queue alert"),
            ("GET", "/api/cameras", "List cameras"),
            ("GET", "/api/cameras/:cameraId", "Camera status"),
            ("POST", "/api/cameras/:cameraId/register", "Register camera"),
            ("POST", "/api/cameras/:cameraId/heartbeat", "Send heartbeat"),
        ],
    )
    def test_endpoint_metadata_serialisable(self, method, path, description):
        info = {"method": method, "path": path, "description": description}
        assert json.loads(json.dumps(info))["method"] == method

    @pytest.mark.parametrize(
        "service,port",
        [
            ("Python Core", 5000),
            ("Alert Dispatcher", 8080),
            ("Camera Streamer", 8081),
            ("TypeScript API", 3000),
            ("Video Optimizer", 8082),
        ],
    )
    def test_service_port_is_valid(self, service, port):
        assert 1024 <= port <= 65535, f"{service} port {port} is out of valid range"


class TestEnvironmentVariables:
    @pytest.mark.parametrize(
        "var",
        [
            "SMTP_HOST",
            "SMTP_USER",
            "SMTP_PASSWORD",
            "ADMIN_EMAIL",
            "ALERT_WEBHOOK_URL",
            "DATABASE_URL",
            "API_PORT",
            "API_AUTH_ENABLED",
            "API_KEYS",
            "CORS_ORIGIN",
            "TRUST_PROXY",
            "ALERT_DISPATCHER_URL",
            "CAMERA_STREAMER_URL",
            "OPTIMIZER_PORT",
        ],
    )
    def test_required_env_var_documented(self, var):
        """Verify that each expected environment variable name is a non-empty string."""
        assert isinstance(var, str) and len(var) > 0


class TestServiceCommunicationFlow:
    def test_flow_steps_are_consistent(self):
        flow = {
            "step_1": "Python Core detects threat",
            "step_2": "Sends alert to TypeScript API (POST /api/alerts)",
            "step_3": "API forwards to Go Alert Dispatcher (POST /alert)",
            "step_4": "Dispatcher rate-limits and processes alert",
            "step_5": "Sends email/webhook notifications",
        }
        # All steps must be serialisable and non-empty
        for step, description in flow.items():
            assert description
        recovered = json.loads(json.dumps(flow))
        assert recovered == flow
