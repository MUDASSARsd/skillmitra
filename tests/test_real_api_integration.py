"""
Optional Manual Integration Test Script for Live LLM API Calls.
Requires a valid GEMINI_API_KEY, GROQ_API_KEY, or OPENAI_API_KEY environment variable.
Run manually: python tests/test_real_api_integration.py
"""
import os
import json
from dotenv import load_dotenv
from backend.nlu.online_extractor import OnlineProfileExtractor
from backend.models.beneficiary import BeneficiaryProfile

load_dotenv()


def main():
    api_key = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GROQ_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )
    provider = os.getenv("LLM_PROVIDER", "gemini")

    if not api_key:
        print("==================================================================")
        print("MANUAL REAL API INTEGRATION TEST SKIPPED")
        print("No API Key found in environment (GEMINI_API_KEY / GROQ_API_KEY / OPENAI_API_KEY).")
        print("To run live API tests, set GEMINI_API_KEY=your_key in .env and run this script.")
        print("==================================================================")
        return

    print(f"Connecting to live LLM Provider: {provider}")
    extractor = OnlineProfileExtractor(provider=provider, api_key=api_key)

    test_inputs = [
        "Maine 10th complete kiya hai. Mere uncle ke saath 2 saal electrical wiring ka kaam kiya. Hyderabad mein rehta hoon aur mujhe electrician ka proper course karke job chahiye.",
        "Main 12th pass hoon lekin mere paas koi kaam ka experience nahi hai.",
        "Warangal mein khud ka plumbing shop start karna chahta hoon."
    ]

    current_profile = BeneficiaryProfile()

    for idx, text in enumerate(test_inputs, 1):
        print(f"\n--- LIVE TURN {idx} ---")
        print(f"User: \"{text}\"")
        try:
            current_profile = extractor.extract(text, current_profile=current_profile)
            print("Updated Profile:")
            print(current_profile.model_dump_json(indent=2))
        except Exception as e:
            print(f"Error during extraction: {e}")


if __name__ == "__main__":
    main()
