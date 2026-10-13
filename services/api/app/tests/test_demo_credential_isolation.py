import os
import glob
import pytest
from app.core.config import settings
from app.db.seed import seed_database
from app.models.entities import User, UserRole


def test_seed_database_refuses_production_environment(db_session):
    """
    Security Verification:
    Ensures that seed_database unconditionally refuses to execute in production environments,
    preventing known demonstration credentials or administrator passwords from ever being seeded.
    Also verifies that existing user accounts remain intact and unmodified.
    """
    # 1. Create a baseline existing user
    baseline_user = User(
        email="real_operator@city.gov",
        hashed_password="secure_argon_hash",
        display_name="City Operator",
        role=UserRole.OPERATOR,
    )
    db_session.add(baseline_user)
    db_session.commit()
    baseline_id = baseline_user.id

    orig_env = settings.ENVIRONMENT
    orig_db = settings.DATABASE_URL
    try:
        # Simulate production environment setting
        settings.ENVIRONMENT = "production"

        with pytest.raises(RuntimeError, match="SECURITY ABORT: Demo database seeding is strictly prohibited in production"):
            seed_database()

        # Simulate prod term in environment
        settings.ENVIRONMENT = "prod"
        with pytest.raises(RuntimeError, match="SECURITY ABORT"):
            seed_database()

        # Simulate production database URL
        settings.ENVIRONMENT = "development"
        settings.DATABASE_URL = "postgresql://user:pass@production-cluster:5432/civictrace_prod"
        with pytest.raises(RuntimeError, match="SECURITY ABORT"):
            seed_database()

        # Verify existing user accounts were untouched
        reloaded = db_session.query(User).filter(User.id == baseline_id).first()
        assert reloaded is not None
        assert reloaded.email == "real_operator@city.gov"
        assert reloaded.hashed_password == "secure_argon_hash"

        # Verify no demo admin was inserted
        demo_admin = db_session.query(User).filter(User.email == "admin@civictrace.local").first()
        assert demo_admin is None

    finally:
        settings.ENVIRONMENT = orig_env
        settings.DATABASE_URL = orig_db


def test_production_web_distribution_excludes_demo_credentials():
    """
    Security Verification:
    Inspects built production JavaScript assets in apps/web/dist/assets/ (if built)
    to confirm that bundler dead-code elimination has stripped all known demo passwords
    and one-click seed controls.
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    dist_assets_dir = os.path.join(project_root, "apps", "web", "dist", "assets")

    # If production build has been generated, assert zero instances of demo passwords
    if os.path.exists(dist_assets_dir):
        js_files = glob.glob(os.path.join(dist_assets_dir, "*.js"))
        assert len(js_files) > 0, "Expected at least one compiled JS bundle in apps/web/dist/assets"

        forbidden_strings = [
            "AdminPass2026!",
            "CitizenPass2026!",
            "ReviewerPass2026!",
            "OperatorPass2026!",
            "One-Click Seed Accounts",
        ]

        for js_file in js_files:
            with open(js_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for forbidden in forbidden_strings:
                    assert forbidden not in content, (
                        f"Found forbidden demo credential or control '{forbidden}' in production build {os.path.basename(js_file)}"
                    )
