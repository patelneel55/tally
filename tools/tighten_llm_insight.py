"""
Tools for improving and tightening LLM-generated financial insights.
"""
from openai import OpenAI
from ai_analyst.app.core.config import settings
import logging

# Set up logging
logger = logging.getLogger(__name__)

def tighten_llm_insight(summary: str) -> str:
    """
    Sharpens a raw LLM summary using a professional equity research analyst tone.
    """
    # Initialize OpenAI client with API key from settings
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    system_msg = {
        "role": "system",
        "content": (
            "You are a senior equity research analyst at a top-tier investment firm. "
            "Your summary will be read by hundreds of institutional investors, including CIOs, PMs, and potentially someone like Warren Buffett. "
            "There is no room for fluff or vagueness. Be specific. Use real numbers from the input. Highlight material risks, segment trends, capital strength, and valuation-relevant insight. "
            "Write as if this is going in a published stock pitch or research note."
        )
    }

    user_msg = {
        "role": "user",
        "content": (
            "Here is a first draft of a financial summary. "
            "Rewrite it to be sharper, more professional, and more financially insightful:\n\n"
            f"{summary}"
        )
    }

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[system_msg, user_msg],
            temperature=0.4,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error tightening summary: {e}")
        return f"Error tightening summary: {str(e)}" 