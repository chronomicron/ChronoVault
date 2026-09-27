"""
test_analyze_date_agreement.py

A focused regression test for analyze_date's scoring logic. It verifies
that mismatch_threshold_days is treated as an exact elapsed-time
tolerance: times just inside and exactly at the limit agree, while times
just outside it disagree in either direction.

This test lives in test_functions/ alongside the project's manual
diagnostics, but it is an automated unittest. It substitutes controlled
date signals for metadata extraction, so it does not read or modify
media, databases, archives, reports, or configuration.

To try this (from the ChronoVault/ project root), run:
    python3 -m unittest -v test_functions.test_analyze_date_agreement
"""

import importlib
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch


analyzer = importlib.import_module('analyze_date.analyze_date')


class ExactDateAgreementTests(unittest.TestCase):
    primary_date = datetime(2020, 1, 1, 12, 0, 0)
    tolerance = timedelta(days=1)
    epsilon = timedelta(microseconds=1)

    def analyze_with_offset(self, offset):
        signals = [
            {
                'date': self.primary_date,
                'source': 'exif_original',
                'base_confidence': 95,
            },
            {
                'date': self.primary_date + offset,
                'source': 'filename_pattern',
                'base_confidence': 70,
            },
        ]
        with patch.object(analyzer, 'gather_signals', return_value=(signals, None)):
            return analyzer.analyze_date({
                'file_path': 'unused',
                'mismatch_threshold_days': 1,
            })

    def test_times_just_inside_tolerance_agree(self):
        for offset in (self.tolerance - self.epsilon, -self.tolerance + self.epsilon):
            with self.subTest(offset=offset):
                result = self.analyze_with_offset(offset)
                self.assertEqual(result['confidence'], 100)
                self.assertIn('confirmed by filename date pattern', result['reason'])

    def test_times_exactly_at_tolerance_agree(self):
        for offset in (self.tolerance, -self.tolerance):
            with self.subTest(offset=offset):
                result = self.analyze_with_offset(offset)
                self.assertEqual(result['confidence'], 100)
                self.assertIn('confirmed by filename date pattern', result['reason'])

    def test_times_just_outside_tolerance_disagree(self):
        for offset in (self.tolerance + self.epsilon, -self.tolerance - self.epsilon):
            with self.subTest(offset=offset):
                result = self.analyze_with_offset(offset)
                self.assertEqual(result['confidence'], 70)
                self.assertIn('disagrees with filename date pattern', result['reason'])


if __name__ == '__main__':
    unittest.main()
