import unittest

from stryder_core.profile_memory import check_boot_json




class TestCheckBootJson(unittest.TestCase):
        
    def test_missing_active_profile_key(self):
        data = {
            "profiles": {}
        }
        status = check_boot_json(data)
        self.assertEqual(status, 'invalid')
    
    def test_missing_profiles_key(self):
        data = {
            "active_profile": "default"
        }
        status = check_boot_json(data)
        self.assertEqual(status, 'invalid')
    
    def test_active_profile_not_string(self):
        data = {
            "active_profile": 123,
            "profiles": {}
        }
        status = check_boot_json(data)
        self.assertEqual(status, 'invalid')

    def test_profiles_not_dict(self):
        data = {
            "active_profile": "default",
            "profiles": "bug"
        }
        status = check_boot_json(data)
        self.assertEqual(status, 'invalid')

    def test_active_profile_not_in_profiles(self):
        data = {
            "active_profile": "default",
            "profiles": {
                "bug": {}
            }
        }
        status = check_boot_json(data)
        self.assertEqual(status, 'invalid')

    def test_inner_profile_not_dict(self):
        data = {
            "active_profile": "default",
            "profiles": {
                "default": "bug"
            }
        }
        status = check_boot_json(data)
        self.assertEqual(status, 'invalid')

    def test_no_timezone(self):
        data = {
            "active_profile": "default",
            "profiles": {
                "default": {}
            }
        }
        status = check_boot_json(data)
        self.assertEqual(status, 'needs_setup')
    
    def test_timezone_not_string(self):
        data = {
            "active_profile": "default",
            "profiles": {
                "default": {
                    "timezone": 123
                }
            }
        }
        status = check_boot_json(data)
        self.assertEqual(status, 'needs_setup')

    def test_timezone_not_common_timezones(self):
        data = {
            "active_profile": "default",
            "profiles": {
                "default": {
                    "timezone": "bug"
                }
            }
        }
        status = check_boot_json(data)
        self.assertEqual(status, 'needs_setup')
    
    def test_valid_profile_returns_valid(self):
        data = {
            "active_profile": "test name",
            "profiles": {
                "test name": {
                "timezone": "Europe/Athens"
                }
            }
        }
        status = check_boot_json(data)
        self.assertEqual(status, 'valid')