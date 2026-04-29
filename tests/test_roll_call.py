"""
Tests for RollCall and IdentityResult.

The ``face_recognition`` library (dlib-based) is not installed in CI.
All tests verify the graceful-fallback path where "Unknown" is returned
and no exception is raised.
"""

import numpy as np
import pytest

from src.attendance.roll_call import IdentityResult, RollCall

# ---------------------------------------------------------------------------
# IdentityResult dataclass
# ---------------------------------------------------------------------------


class TestIdentityResult:
    def test_known_identity(self):
        r = IdentityResult(name="Alice", confidence=0.85, is_known=True)
        assert r.name == "Alice"
        assert r.is_known is True
        assert r.confidence == pytest.approx(0.85)

    def test_unknown_identity(self):
        r = IdentityResult(name=RollCall.UNKNOWN, confidence=0.0, is_known=False)
        assert r.name == "Unknown"
        assert not r.is_known

    def test_confidence_is_zero_for_unknown(self):
        r = IdentityResult(name="Unknown", confidence=0.0, is_known=False)
        assert r.confidence == 0.0


# ---------------------------------------------------------------------------
# RollCall
# ---------------------------------------------------------------------------


class TestRollCall:
    def test_init_nonexistent_dir_does_not_raise(self, tmp_path):
        """RollCall must start gracefully when the faces directory is absent."""
        rc = RollCall(known_faces_dir=str(tmp_path / "no_such_dir"))
        assert rc.registered_names == []

    def test_init_empty_dir(self, tmp_path):
        rc = RollCall(known_faces_dir=str(tmp_path))
        assert rc.registered_names == []

    def test_identify_without_face_recognition_returns_unknown(self, tmp_path):
        """identify() must return Unknown when face_recognition is absent."""
        rc = RollCall(known_faces_dir=str(tmp_path))
        crop = np.zeros((60, 60, 3), dtype=np.uint8)
        result = rc.identify(crop)
        assert result.name == RollCall.UNKNOWN
        assert not result.is_known
        assert result.confidence == 0.0

    def test_registered_names_empty_without_loaded_faces(self, tmp_path):
        rc = RollCall(known_faces_dir=str(tmp_path))
        assert rc.registered_names == []

    def test_identify_returns_unknown_when_no_encodings_loaded(self, tmp_path):
        """Even if face_recognition were present but no faces loaded, Unknown."""
        rc = RollCall(known_faces_dir=str(tmp_path))
        assert rc._known_encodings == {}
        crop = np.zeros((60, 60, 3), dtype=np.uint8)
        result = rc.identify(crop)
        assert result.name == RollCall.UNKNOWN

    def test_tolerance_stored(self, tmp_path):
        rc = RollCall(known_faces_dir=str(tmp_path), tolerance=0.3)
        assert rc._tolerance == pytest.approx(0.3)

    def test_default_tolerance(self, tmp_path):
        rc = RollCall(known_faces_dir=str(tmp_path))
        assert rc._tolerance == pytest.approx(0.5)

    def test_dir_with_non_dir_entries_ignored(self, tmp_path):
        """Files in the root of known_faces_dir should be skipped safely."""
        (tmp_path / "readme.txt").write_text("not a person dir")
        rc = RollCall(known_faces_dir=str(tmp_path))
        assert rc.registered_names == []

    def test_person_dir_without_images_ignored(self, tmp_path):
        """A person sub-directory with no valid images leaves registered empty."""
        person_dir = tmp_path / "Alice"
        person_dir.mkdir()
        (person_dir / "notes.txt").write_text("not an image")
        rc = RollCall(known_faces_dir=str(tmp_path))
        assert "Alice" not in rc.registered_names
