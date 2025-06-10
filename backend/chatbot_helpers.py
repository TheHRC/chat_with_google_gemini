import os
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()


# Load
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-pro')


def chatbot(user_input):
    # Get the response from
    response = model.generate_content(user_input)

    # Uncomment this if stream is true
    # for chunk in response:
    #     yield chunk.text
    return response.text
