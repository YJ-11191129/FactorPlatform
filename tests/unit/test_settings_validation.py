import unittest

from app.core.settings import Settings, validate_runtime_settings


class TestSettingsValidation(unittest.TestCase):
    def test_dev_allows_incomplete_settings(self) -> None:
        validate_runtime_settings(Settings(env="dev", require_db=False, require_auth=False, api_keys=""))

    def test_prod_requires_db_auth_and_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "REQUIRE_DB"):
            validate_runtime_settings(Settings(env="prod", require_db=False, require_auth=True, api_keys="real-key:admin"))

        with self.assertRaisesRegex(ValueError, "REQUIRE_AUTH"):
            validate_runtime_settings(Settings(env="production", require_db=True, require_auth=False, api_keys="real-key:admin"))

        with self.assertRaisesRegex(ValueError, "API_KEYS"):
            validate_runtime_settings(Settings(env="prod", require_db=True, require_auth=True, api_keys=""))

    def test_prod_rejects_placeholder_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "placeholder"):
            validate_runtime_settings(Settings(env="prod", require_db=True, require_auth=True, api_keys="CHANGE_ME_ADMIN_KEY:admin"))

    def test_prod_accepts_realistic_keys(self) -> None:
        validate_runtime_settings(Settings(env="prod", require_db=True, require_auth=True, api_keys="fp_live_abc123:admin,fp_view_xyz789:viewer"))


if __name__ == "__main__":
    unittest.main()
