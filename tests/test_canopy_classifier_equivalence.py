import os
import sys
import unittest
import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from ml.canopy_classifier import (
    compute_spectral_indices,
    classify_sugarcane_pixel,
    classify_sugarcane_raster,
    SCL_VALID_CLASSES
)

class TestCanopyClassifierEquivalence(unittest.TestCase):

    def test_spectral_indices_consistency(self):
        b2, b3, b4, b5, b8, b11 = 0.035, 0.075, 0.045, 0.125, 0.485, 0.165
        
        scalar_ind = compute_spectral_indices(b2, b3, b4, b5, b8, b11)
        
        b2_arr = np.array([[b2, b2 * 1.1]])
        b3_arr = np.array([[b3, b3 * 1.1]])
        b4_arr = np.array([[b4, b4 * 1.1]])
        b5_arr = np.array([[b5, b5 * 1.1]])
        b8_arr = np.array([[b8, b8 * 1.1]])
        b11_arr = np.array([[b11, b11 * 1.1]])
        
        vec_ind = compute_spectral_indices(b2_arr, b3_arr, b4_arr, b5_arr, b8_arr, b11_arr)
        
        self.assertAlmostEqual(scalar_ind["ndvi"], float(vec_ind["ndvi"][0, 0]), places=6)
        self.assertAlmostEqual(scalar_ind["ndre"], float(vec_ind["ndre"][0, 0]), places=6)
        self.assertAlmostEqual(scalar_ind["lswi"], float(vec_ind["lswi"][0, 0]), places=6)
        self.assertAlmostEqual(scalar_ind["ndwi"], float(vec_ind["ndwi"][0, 0]), places=6)
        self.assertAlmostEqual(scalar_ind["bsi"], float(vec_ind["bsi"][0, 0]), places=6)

    def test_classifier_mathematical_equivalence(self):
        np.random.seed(42)
        n_samples = 250
        
        ndvis = np.random.uniform(0.1, 0.9, n_samples)
        ndres = np.random.uniform(-0.1, 0.5, n_samples)
        lswis = np.random.uniform(-0.1, 0.4, n_samples)
        ndwis = np.random.uniform(-0.3, 0.2, n_samples)
        bsis  = np.random.uniform(-0.2, 0.3, n_samples)
        scls  = np.random.choice([3, 4, 5, 6, 7, 8, 9], n_samples)
        
        scalar_results = []
        for i in range(n_samples):
            res = classify_sugarcane_pixel(
                float(ndvis[i]), float(ndres[i]), float(lswis[i]),
                float(ndwis[i]), float(bsis[i]), int(scls[i])
            )
            scalar_results.append(res["is_standing_cane"])
            
        vec_results = classify_sugarcane_raster(
            ndvis, ndres, lswis, scls, ndwis, bsis
        )
        
        np.testing.assert_array_equal(scalar_results, vec_results)
        print(f"PASS: Verified {n_samples} random test cases. 100% exact mathematical match between scalar and vectorized classifiers.")

if __name__ == "__main__":
    unittest.main()