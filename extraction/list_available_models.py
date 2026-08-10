"""
Run this once to see exactly which models YOUR API key can currently use.
Model names change fast — this avoids guessing.

Usage: python list_available_models.py
"""

import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

print("Models available to your API key that support image+text generation:\n")
for model in genai.list_models():
    if "generateContent" in model.supported_generation_methods:
        print(f"  {model.name}")

print("\nCopy one of the names above (without the 'models/' prefix) into MODEL_NAME in gemini_extract.py")