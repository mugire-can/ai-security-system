"""
Integration tests — checks that all multi-language service files exist and
the toolchain is correctly structured.

These tests verify file structure and service configuration without
requiring Docker, Go, Node.js, or Rust to be installed.  Missing
compilers/runtimes cause those specific checks to be skipped rather
than fail.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

_BASE = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# File-structure checks
# ---------------------------------------------------------------------------


class TestFileStructure:
    @pytest.mark.parametrize(
        "rel_path,description",
        [
            (".github/CODEOWNERS", "CODEOWNERS"),
            (".github/dependabot.yml", "Dependabot configuration"),
            (".github/pull_request_template.md", "Pull request template"),
            (".github/ISSUE_TEMPLATE/bug_report.yml", "Bug report issue form"),
            (".github/ISSUE_TEMPLATE/feature_request.yml", "Feature request issue form"),
            (".pre-commit-config.yaml", "Pre-commit configuration"),
            ("Taskfile.yml", "Task runner configuration"),
            ("SECURITY.md", "Security policy"),
            ("CHANGELOG.md", "Changelog"),
            (".env.production.example", "Production environment template"),
            ("docker-compose.prod.yml", "Production Docker Compose file"),
            ("evaluation/manifest.example.json", "Evaluation manifest example"),
            ("scripts/validate_evaluation_manifest.py", "Evaluation validation script"),
            ("services/go/alert_dispatcher/main.go", "Go Alert Dispatcher"),
            ("services/go/alert_dispatcher/go.mod", "Go Alert Dispatcher Module"),
            ("services/go/camera_streamer/main.go", "Go Camera Streamer"),
            ("services/go/camera_streamer/go.mod", "Go Camera Streamer Module"),
            ("services/typescript/api/package.json", "TypeScript API"),
            ("services/typescript/api/tsconfig.json", "TypeScript Config"),
            ("services/typescript/api/src/server.ts", "TypeScript Server"),
            ("services/rust/video_optimizer/Cargo.toml", "Rust Video Optimizer"),
            ("services/rust/video_optimizer/src/main.rs", "Rust Main"),
            ("docker-compose.yml", "Docker Compose"),
            ("Dockerfile.python", "Python Dockerfile"),
            ("README.md", "Project documentation"),
            (".github/workflows/release.yml", "Release workflow"),
        ],
    )
    def test_required_file_exists(self, rel_path, description):
        assert (_BASE / rel_path).exists(), f"{description} not found: {rel_path}"


class TestPythonCoreIntegrity:
    @pytest.mark.parametrize(
        "rel_path",
        [
            "main.py",
            "config/settings.py",
            "src/pipeline.py",
            "requirements.txt",
            "pyproject.toml",
        ],
    )
    def test_python_core_file_exists(self, rel_path):
        assert (_BASE / rel_path).exists(), f"Core file missing: {rel_path}"


# ---------------------------------------------------------------------------
# Go service structure checks
# ---------------------------------------------------------------------------


class TestGoServices:
    @pytest.mark.parametrize("service", ["alert_dispatcher", "camera_streamer"])
    def test_go_mod_is_valid(self, service):
        mod_path = _BASE / "services" / "go" / service / "go.mod"
        assert mod_path.exists()
        content = mod_path.read_text()
        assert "module" in content
        assert "go 1" in content

    @pytest.mark.parametrize("service", ["alert_dispatcher", "camera_streamer"])
    def test_main_go_exists(self, service):
        assert (_BASE / "services" / "go" / service / "main.go").exists()

    def test_go_fmt_alert_dispatcher(self):
        """If Go is installed, verify the alert dispatcher is well-formatted."""
        svc_dir = _BASE / "services" / "go" / "alert_dispatcher"
        try:
            result = subprocess.run(
                ["go", "fmt", "-l", "main.go"],
                cwd=svc_dir,
                capture_output=True,
                text=True,
            )
        except OSError:
            pytest.skip("Go toolchain check not supported in this environment")
        if result.returncode != 0 and "exec" in (result.stderr or ""):
            pytest.skip("Go not installed")
        # go fmt -l prints files with formatting issues; empty output = clean
        assert result.stdout.strip() == "", "alert_dispatcher/main.go has formatting issues"


# ---------------------------------------------------------------------------
# TypeScript API checks
# ---------------------------------------------------------------------------


class TestTypescriptApi:
    def test_package_json_is_valid(self):
        pkg_path = _BASE / "services" / "typescript" / "api" / "package.json"
        with open(pkg_path) as f:
            data = json.load(f)
        assert "dependencies" in data
        assert "devDependencies" in data

    def test_tsconfig_has_compiler_options(self):
        tsconfig = _BASE / "services" / "typescript" / "api" / "tsconfig.json"
        with open(tsconfig) as f:
            data = json.load(f)
        assert "compilerOptions" in data

    def test_server_ts_is_express_app(self):
        server = (_BASE / "services" / "typescript" / "api" / "src" / "server.ts").read_text()
        assert "import express" in server
        assert "app.listen" in server


# ---------------------------------------------------------------------------
# Rust service checks
# ---------------------------------------------------------------------------


class TestRustService:
    def test_cargo_toml_valid(self):
        cargo = (_BASE / "services" / "rust" / "video_optimizer" / "Cargo.toml").read_text()
        assert "[package]" in cargo
        assert 'name = "video_optimizer"' in cargo

    def test_main_rs_uses_tokio(self):
        main_rs = (_BASE / "services" / "rust" / "video_optimizer" / "src" / "main.rs").read_text()
        assert "#[tokio::main]" in main_rs
        assert "warp::serve" in main_rs


# ---------------------------------------------------------------------------
# Docker configuration checks
# ---------------------------------------------------------------------------


class TestDockerSetup:
    def test_docker_compose_has_all_services(self):
        compose = (_BASE / "docker-compose.yml").read_text()
        for service in (
            "python-core",
            "alert_dispatcher",
            "camera_streamer",
            "api",
            "video_optimizer",
            "postgres",
            "redis",
        ):
            assert service in compose, f"Service '{service}' not in docker-compose.yml"

    @pytest.mark.parametrize(
        "dockerfile_path",
        [
            "Dockerfile.python",
            "services/go/alert_dispatcher/Dockerfile",
            "services/go/camera_streamer/Dockerfile",
            "services/typescript/api/Dockerfile",
            "services/rust/video_optimizer/Dockerfile",
        ],
    )
    def test_dockerfile_exists(self, dockerfile_path):
        assert (_BASE / dockerfile_path).exists(), f"Missing: {dockerfile_path}"


# ---------------------------------------------------------------------------
# Evaluation scaffold checks
# ---------------------------------------------------------------------------


class TestEvaluationScaffold:
    def test_manifest_example_is_valid(self):
        from scripts.validate_evaluation_manifest import validate_manifest

        errors = validate_manifest(_BASE / "evaluation" / "manifest.example.json")
        assert errors == []
