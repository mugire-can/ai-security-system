#!/usr/bin/env python3
"""
Database Setup & Migration Script

Initializes the database with proper schema and optional test data.
Supports SQLite (development) and PostgreSQL (production).

Usage:
    python scripts/setup_database.py              # Initialize with default settings
    python scripts/setup_database.py --seed       # Add test data
    python scripts/setup_database.py --reset      # Drop and recreate (WARNING: data loss!)
    python scripts/setup_database.py --backup     # Backup current database
"""

import argparse
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import AppConfig, DatabaseConfig
from src.database.db_manager import (
    AlertRecord,
    AnomalyEvent,
    AttendanceRecord,
    BehaviourEvent,
    DatabaseManager,
    DetectionEvent,
)


class DatabaseSetup:
    """Handle database initialization and migration."""

    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.getenv("DATABASE_URL", "sqlite:///data/security_system.db")
        self.db_manager = DatabaseManager(self.db_url)
        self.is_sqlite = "sqlite" in self.db_url
        self.is_postgres = "postgresql" in self.db_url

    def initialize(self, verbose: bool = True) -> bool:
        """
        Initialize database schema.

        Creates all required tables if they don't exist.
        Safe to run multiple times (idempotent).

        Returns:
            bool: True if successful, False if error
        """
        try:
            if verbose:
                print(f"📦 Initializing database...")
                print(f"   Database: {self._mask_url(self.db_url)}")

            # Database manager automatically creates tables in __init__
            # via Base.metadata.create_all()

            if verbose:
                print(f"✅ Database initialized successfully!")
                self._print_db_info()
            return True

        except Exception as e:
            print(f"❌ Error initializing database: {e}")
            return False

    def reset(self, confirm: bool = True) -> bool:
        """
        Drop all tables and reinitialize (DESTRUCTIVE).

        WARNING: This deletes all data!

        Args:
            confirm: If True, ask for confirmation before proceeding

        Returns:
            bool: True if successful
        """
        if confirm:
            response = input(
                "⚠️  WARNING: This will DELETE ALL DATA in the database!\n"
                "Type 'yes' to confirm: "
            )
            if response.lower() != "yes":
                print("Reset cancelled.")
                return False

        try:
            print("🔄 Dropping all tables...")
            from src.database.db_manager import Base

            Base.metadata.drop_all(bind=self.db_manager._engine)

            print("🔄 Recreating schema...")
            Base.metadata.create_all(bind=self.db_manager._engine)

            print("✅ Database reset successfully!")
            return True

        except Exception as e:
            print(f"❌ Error resetting database: {e}")
            return False

    def seed_test_data(self, verbose: bool = True) -> bool:
        """
        Populate database with realistic test data for development.

        Returns:
            bool: True if successful
        """
        try:
            if verbose:
                print("🌱 Seeding test data...")

            session = self.db_manager.session()

            # Sample detection events
            detections = [
                DetectionEvent(
                    camera_id="cam-01",
                    zone="classroom-A",
                    object_type="person",
                    confidence=0.92,
                    person_name="Alice Smith",
                    timestamp=datetime.now() - timedelta(hours=2),
                ),
                DetectionEvent(
                    camera_id="cam-02",
                    zone="entrance",
                    object_type="vehicle",
                    confidence=0.87,
                    timestamp=datetime.now() - timedelta(hours=1),
                ),
                DetectionEvent(
                    camera_id="cam-01",
                    zone="corridor",
                    object_type="person",
                    confidence=0.79,
                    person_name="Bob Jones",
                    timestamp=datetime.now() - timedelta(minutes=30),
                ),
            ]

            for det in detections:
                session.add(det)

            # Sample behavior events
            behaviors = [
                BehaviourEvent(
                    camera_id="cam-01",
                    zone="classroom-A",
                    detection_id=1,
                    person_name="Alice Smith",
                    activity="loitering",
                    emotion="neutral",
                    suspicion_score=0.3,
                    is_suspicious=False,
                    timestamp=datetime.now() - timedelta(hours=1),
                ),
                BehaviourEvent(
                    camera_id="cam-01",
                    zone="corridor",
                    detection_id=3,
                    person_name="Bob Jones",
                    activity="running",
                    emotion="angry",
                    suspicion_score=0.8,
                    is_suspicious=True,
                    timestamp=datetime.now() - timedelta(minutes=45),
                ),
            ]

            for beh in behaviors:
                session.add(beh)

            # Sample anomaly events
            anomalies = [
                AnomalyEvent(
                    camera_id="cam-02",
                    zone="entrance",
                    anomaly_type="animal_detected",
                    object_class="dog",
                    confidence=0.79,
                    description="Dog detected in entrance zone",
                    timestamp=datetime.now() - timedelta(minutes=30),
                ),
                AnomalyEvent(
                    camera_id="cam-01",
                    zone="classroom-A",
                    anomaly_type="unattended_object",
                    object_class="backpack",
                    confidence=0.65,
                    description="Unattended backpack near window",
                    timestamp=datetime.now() - timedelta(minutes=15),
                ),
            ]

            for anom in anomalies:
                session.add(anom)

            # Sample alert records
            alerts = [
                AlertRecord(
                    severity="high",
                    alert_type="anomaly",
                    camera_id="cam-02",
                    zone="entrance",
                    person_name=None,
                    description="Animal detected in restricted area",
                    acknowledged=False,
                    sent=True,
                    timestamp=datetime.now() - timedelta(minutes=30),
                ),
                AlertRecord(
                    severity="medium",
                    alert_type="loitering",
                    camera_id="cam-01",
                    zone="corridor",
                    person_name="Carol White",
                    description="Person loitering for >2 minutes",
                    acknowledged=True,
                    sent=True,
                    timestamp=datetime.now() - timedelta(hours=1),
                ),
                AlertRecord(
                    severity="high",
                    alert_type="suspicious_behaviour",
                    camera_id="cam-01",
                    zone="classroom-A",
                    person_name="Bob Jones",
                    description="Suspicious running behavior detected",
                    acknowledged=False,
                    sent=True,
                    timestamp=datetime.now() - timedelta(minutes=45),
                ),
            ]

            for alert in alerts:
                session.add(alert)

            # Sample attendance records
            from datetime import time

            attendance = [
                AttendanceRecord(
                    person_name="Alice Smith",
                    camera_id="cam-01",
                    zone="entrance",
                    check_in=datetime.combine(datetime.today().date(), time(8, 15)),
                    check_out=datetime.combine(datetime.today().date(), time(17, 45)),
                    duration_minutes=510,
                    status="late",
                    date=datetime.today().strftime("%Y-%m-%d"),
                ),
                AttendanceRecord(
                    person_name="Bob Jones",
                    camera_id="cam-01",
                    zone="entrance",
                    check_in=datetime.combine(datetime.today().date(), time(7, 55)),
                    check_out=datetime.combine(datetime.today().date(), time(17, 30)),
                    duration_minutes=575,
                    status="present",
                    date=datetime.today().strftime("%Y-%m-%d"),
                ),
                AttendanceRecord(
                    person_name="Carol White",
                    camera_id="cam-01",
                    zone="entrance",
                    check_in=None,
                    check_out=None,
                    duration_minutes=0,
                    status="absent",
                    date=datetime.today().strftime("%Y-%m-%d"),
                ),
            ]

            for att in attendance:
                session.add(att)

            session.commit()

            if verbose:
                print(f"✅ Seeded {len(detections)} detection events")
                print(f"✅ Seeded {len(behaviors)} behavior events")
                print(f"✅ Seeded {len(anomalies)} anomaly events")
                print(f"✅ Seeded {len(alerts)} alert records")
                print(f"✅ Seeded {len(attendance)} attendance records")
                self._print_db_info()

            return True

        except Exception as e:
            try:
                session.rollback()
            except Exception:  # nosec B110
                pass
            print(f"❌ Error seeding test data: {e}")
            import traceback

            traceback.print_exc()
            return False

        finally:
            try:
                session.close()
            except Exception:  # nosec B110
                pass

    def backup(self, output_file: str = None) -> bool:
        """
        Create a backup of the current database.

        Args:
            output_file: Path to backup file (default: data/backups/db_TIMESTAMP.backup)

        Returns:
            bool: True if successful
        """
        try:
            if not output_file:
                backup_dir = Path("data/backups")
                backup_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = backup_dir / f"db_{timestamp}.backup"
            else:
                output_file = Path(output_file)

            if self.is_sqlite:
                db_file = self.db_url.replace("sqlite:///", "")
                if Path(db_file).exists():
                    import shutil

                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(db_file, output_file)
                    print(f"✅ Database backed up to: {output_file}")
                    return True
                else:
                    print(f"❌ Database file not found: {db_file}")
                    return False
            else:
                print("⚠️  Backup not implemented for PostgreSQL yet")
                return False

        except Exception as e:
            print(f"❌ Error backing up database: {e}")
            return False

    def _print_db_info(self):
        """Print database information."""
        print(f"\n📊 Database Information:")
        print(f"   Type: {'SQLite' if self.is_sqlite else 'PostgreSQL'}")
        print(f"   URL: {self._mask_url(self.db_url)}")
        if self.is_sqlite:
            db_file = self.db_url.replace("sqlite:///", "")
            if Path(db_file).exists():
                size_mb = Path(db_file).stat().st_size / (1024 * 1024)
                print(f"   Size: {size_mb:.2f} MB")

    def _mask_url(self, url: str) -> str:
        """Mask sensitive info in database URL."""
        if "postgresql" in url and "@" in url:
            parts = url.split("@")
            return f"postgresql://***:***@{parts[1]}"
        return url


def main():
    parser = argparse.ArgumentParser(
        description="Database setup and migration tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/setup_database.py                    # Initialize
  python scripts/setup_database.py --seed             # Initialize + test data
  python scripts/setup_database.py --backup           # Backup current DB
  python scripts/setup_database.py --reset --no-ask   # Reset without confirmation
        """,
    )

    parser.add_argument(
        "--seed",
        action="store_true",
        help="Populate with test data after initialization",
    )
    parser.add_argument(
        "--reset", action="store_true", help="Drop and recreate database (DESTRUCTIVE)"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create backup of current database",
    )
    parser.add_argument("--output", default=None, help="Output file for backup (with --backup)")
    parser.add_argument(
        "--no-ask",
        action="store_true",
        help="Skip confirmation prompt for destructive operations",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="Override DATABASE_URL env var",
    )

    args = parser.parse_args()

    # Create setup instance
    setup = DatabaseSetup(db_url=args.db_url)

    # Execute requested operations
    if args.reset:
        success = setup.reset(confirm=not args.no_ask)
        if not success:
            sys.exit(1)

    if args.backup:
        success = setup.backup(output_file=args.output)
        sys.exit(0 if success else 1)

    # Default: initialize
    if not args.reset:
        success = setup.initialize()
        if not success:
            sys.exit(1)

    # Optional: seed test data
    if args.seed:
        success = setup.seed_test_data()
        if not success:
            sys.exit(1)

    print(f"\n✅ All done! Database is ready to use.")
    print(f"   Run: python main.py --demo")


if __name__ == "__main__":
    main()
