from __future__ import annotations

import unittest

from db_helpers import sort_test_numbers_desc


class DbHelpersSortTests(unittest.TestCase):
    def test_sort_test_numbers_desc_for_year_and_sequence(self) -> None:
        items = ["2024/001", "2026/010", "2025/120", "2026/002"]
        self.assertEqual(
            sort_test_numbers_desc(items),
            ["2026/010", "2026/002", "2025/120", "2024/001"],
        )

    def test_sort_test_numbers_desc_with_nonstandard_values(self) -> None:
        items = ["TEST-A", "2025-3", "2025-10", "2024/99"]
        self.assertEqual(
            sort_test_numbers_desc(items),
            ["2025-10", "2025-3", "2024/99", "TEST-A"],
        )


if __name__ == "__main__":
    unittest.main()
