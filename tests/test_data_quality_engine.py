import unittest
from ml.data_quality_engine import evaluate_plot_quality


class TestDataQualityEngine(unittest.TestCase):
    def test_gold_grade_a_plot(self):
        report = evaluate_plot_quality(
            plot_no="TEST-A1",
            registered_acres=2.5,
            gps_acres=2.45,
            variety="CO-86032",
            planting_date="2025-11-01",
            crop_age_days=340,
            lab_brix=19.5,
            lab_pol=16.8,
            obs_cloud_pct=5.0,
            obs_ndvi=0.74,
            obs_age_days=8,
            cut_to_crush_hours=12.0,
        )
        self.assertEqual(report["quality_grade"], "A")
        self.assertGreaterEqual(report["trust_score"], 85)
        self.assertTrue(report["eligible_for_harvest"])
        self.assertTrue(report["eligible_for_training"])
        self.assertAlmostEqual(report["purity_pct"], 86.2, places=1)

    def test_fatal_pol_exceeds_brix(self):
        # Dissolved sucrose (Pol) cannot physically exceed total dissolved solids (Brix)
        report = evaluate_plot_quality(
            plot_no="TEST-FATAL",
            registered_acres=2.0,
            variety="CO-265",
            planting_date="2025-10-01",
            crop_age_days=360,
            lab_brix=14.0,
            lab_pol=16.5,
        )
        self.assertEqual(report["quality_grade"], "C")
        self.assertFalse(report["eligible_for_harvest"])
        self.assertFalse(report["eligible_for_training"])
        self.assertTrue(any("cannot exceed Brix" in f for f in report["flags"]))

    def test_stale_cane_and_cloud_contamination(self):
        report = evaluate_plot_quality(
            plot_no="TEST-STALE",
            registered_acres=3.0,
            variety="CO-86032",
            crop_age_days=350,
            lab_brix=18.0,
            lab_pol=15.0,
            obs_cloud_pct=45.0,
            obs_ndvi=0.65,
            cut_to_crush_hours=48.0,
        )
        self.assertIn("STALE_CANE (48h post-cut)", report["flags"])
        self.assertIn("CLOUD_CONTAMINATED (45%)", report["flags"])
        self.assertLess(report["trust_score"], 85)


if __name__ == "__main__":
    unittest.main()
