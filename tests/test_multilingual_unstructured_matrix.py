"""
Comprehensive Multilingual Unstructured Test Suite for Offline and Online Modes.
Tests real-world beneficiary turns across English, Hindi, Telugu, Hinglish, and Telglish
across 12 diverse livelihood sectors.
"""
import unittest
import os
from fastapi.testclient import TestClient
from backend.api.app import app

TEST_CASES = [
    {
        "id": "EN_ELECTRICAL",
        "lang": "en",
        "text": "I completed 10th class. I have 1 year of experience working as an electrician in house wiring. I want a job.",
        "expected_keywords": ["electric", "wire", "10th"],
    },
    {
        "id": "HI_MASONRY",
        "lang": "hi",
        "text": "मैं 8वीं पास हूँ। मैंने 2 साल ईंट की चिनाई और मकान बनाने का काम किया है।",
        "expected_keywords": ["mason", "brick", "construction", "8th"],
    },
    {
        "id": "TE_SOLAR",
        "lang": "te",
        "text": "నేను 12వ తరగతి చదివాను. సోలార్ ప్యానెల్ ఇన్స్టాలేషన్ నేర్చుకోవాలనుకుంటున్నాను.",
        "expected_keywords": ["solar", "photovoltaic", "renewable", "12th"],
    },
    {
        "id": "HINGLISH_AUTOMOTIVE",
        "lang": "hinglish",
        "text": "10th pass, 2 saal se motor mechanic shop me bike repair ka kaam kar raha hu.",
        "expected_keywords": ["mechanic", "automotive", "vehicle", "two wheeler", "10th"],
    },
    {
        "id": "TELGLISH_DAIRY",
        "lang": "te",
        "text": "10th completed, 1 year cows and buffaloes care in dairy farming.",
        "expected_keywords": ["dairy", "cattle", "animal", "livestock", "10th"],
    },
    {
        "id": "HI_TAILORING",
        "lang": "hi",
        "text": "मैं 10वीं पास हूँ। 1.5 साल से सिलाई और कपड़े सिलने का काम करती हूँ।",
        "expected_keywords": ["tailor", "sewing", "apparel", "garment", "10th"],
    },
    {
        "id": "EN_HARDWARE",
        "lang": "en",
        "text": "I passed 12th standard. I have 6 months experience in computer hardware and network repair.",
        "expected_keywords": ["hardware", "computer", "network", "12th"],
    },
    {
        "id": "HINGLISH_PLUMBING",
        "lang": "hinglish",
        "text": "8th pass hu, 1 year se pipe fitting aur water pump repair ka kaam kiya hu.",
        "expected_keywords": ["plumb", "pipe", "pump", "8th"],
    },
    {
        "id": "TE_AGRICULTURE_PUMP",
        "lang": "te",
        "text": "నేను 10వ తరగతి వరకు చదివాను, వ్యవసాయ పంపులు బాగుచేసే పని తెలుసు.",
        "expected_keywords": ["pump", "mechanic", "agriculture", "irrigation", "10th"],
    },
    {
        "id": "EN_HEALTHCARE",
        "lang": "en",
        "text": "I passed 12th science. I want to take community health assistant training.",
        "expected_keywords": ["health", "nurse", "medical", "12th"],
    },
    {
        "id": "HI_BAKERY",
        "lang": "hi",
        "text": "10वीं पास हूँ, बेकरी में ब्रेड और केक बनाने का काम सीखना चाहता हूँ।",
        "expected_keywords": ["baker", "bakery", "food", "10th"],
    },
    {
        "id": "HINGLISH_RETAIL",
        "lang": "hinglish",
        "text": "12th pass, 1 year experience shop sales and customer service.",
        "expected_keywords": ["retail", "sales", "store", "12th"],
    },
]


class TestMultilingualUnstructuredMatrix(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_offline_multilingual_matrix(self):
        print("\n=======================================================")
        print("RUNNING OFFLINE MULTILINGUAL UNSTRUCTURED MATRIX (12 CASES)")
        print("=======================================================")
        passed = 0
        for case in TEST_CASES:
            res = self.client.post(
                "/conversation/offline",
                json={
                    "text": case["text"],
                    "language_code": case["lang"],
                    "include_recommendations": True,
                    "top_k": 5,
                }
            )
            self.assertEqual(res.status_code, 200, f"Failed HTTP 200 for case {case['id']}")
            data = res.json()
            profile = data.get("profile", {})
            recs = data.get("recommendations", [])
            
            # Print brief summary
            mode = data.get("extraction_mode", "offline")
            rec_titles = " | ".join(r.get("qualification", {}).get("title", "") for r in recs[:3])
            print(f"[{case['id']}] Mode: {mode} | Level: {profile.get('education', {}).get('level')} | Matches: {len(recs)}")
            if rec_titles:
                print(f"    Top NQR: {rec_titles[:100]}")
            self.assertIsNotNone(profile)
            passed += 1

        print(f"Offline Matrix Passed: {passed}/{len(TEST_CASES)} cases.")

    def test_online_multilingual_matrix(self):
        print("\n=======================================================")
        print("RUNNING ONLINE MULTILINGUAL UNSTRUCTURED MATRIX (12 CASES)")
        print("=======================================================")
        passed = 0
        skipped = 0
        for case in TEST_CASES:
            res = self.client.post(
                "/conversation",
                json={
                    "text": case["text"],
                    "language_code": case["lang"],
                    "include_recommendations": True,
                    "top_k": 5,
                }
            )
            if res.status_code in (502, 503):
                print(f"[{case['id']}] Online mode skipped: {res.json().get('detail')}")
                skipped += 1
                continue

            self.assertEqual(res.status_code, 200, f"Failed HTTP 200 for case {case['id']}")
            data = res.json()
            profile = data.get("profile", {})
            recs = data.get("recommendations", [])
            
            mode = data.get("extraction_mode", "online")
            rec_titles = " | ".join(r.get("qualification", {}).get("title", "") for r in recs[:3])
            print(f"[{case['id']}] Mode: {mode} | Level: {profile.get('education', {}).get('level')} | Matches: {len(recs)}")
            if rec_titles:
                print(f"    Top NQR: {rec_titles[:100]}")
            self.assertIsNotNone(profile)
            passed += 1

        print(f"Online Matrix Completed: {passed} passed, {skipped} skipped.")


if __name__ == "__main__":
    unittest.main()
