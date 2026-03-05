from __future__ import annotations

import unittest
from unittest.mock import patch

import main


class MainRuntimeTests(unittest.TestCase):
    def test_install_requirements_skips_when_frozen_executable(self) -> None:
        with patch.object(main.sys, "frozen", True, create=True):
            with patch.object(main, "_get_requirements_path") as mocked_requirements:
                with patch.object(main.subprocess, "check_call") as mocked_check_call:
                    main._install_requirements_if_missing()

        mocked_requirements.assert_not_called()
        mocked_check_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
