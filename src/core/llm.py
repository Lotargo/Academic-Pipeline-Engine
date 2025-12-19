import os
from openai import OpenAI
from typing import Optional

class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        # If API key is not set, we run in Mock mode
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    def generate(self, system_prompt: str, user_prompt: str, model: str = "gpt-3.5-turbo") -> str:
        """
        Generates text using an OpenAI-compatible API.
        Returns mock text if no client is initialized.
        """
        if not self.client:
            # Mock behavior for testing/demo without keys
            return f"# Generated Section\n\nThis is a mock response for prompt: {user_prompt[:30]}...\n\nIdeally this would be real academic text."

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"LLM Generation Error: {str(e)}"
