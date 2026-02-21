import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# Environment-configured models / keys
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_TEXT_MODEL', 'gemini-2.5-flash')

def call_gemini_text(prompt, system=None):
	"""Call Google Gemini text API via google.genai library."""
	try:
		client = genai.Client(api_key=GEMINI_API_KEY)
		response = client.models.generate_content(
			model=GEMINI_MODEL,
			contents=prompt
		)
		text = response.text if response else ''
		return {'raw': text}
	except Exception as e:
		print(f'Gemini text error: {e}')
		return {'raw': f'Error: {str(e)}'}

#Testing
if __name__ == "__main__":
    test_prompt = "What is your favorite math concept?"
    result = call_gemini_text(test_prompt)
    print(result['raw'])