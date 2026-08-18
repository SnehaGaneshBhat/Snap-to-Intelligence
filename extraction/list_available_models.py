"""
Run this once to see exactly which models YOUR API key can currently use.
Model names change fast — this avoids guessing.

Usage: python list_available_models.py
"""

import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

print("Models available to your API key that support image+text generation:\n")
for model in client.models.list():
    if "generateContent" in (model.supported_actions or []):
        print(f"  {model.name}")

print("\nCopy one of the names above (without the 'models/' prefix) into MODEL_NAME in gemini_extract.py")
