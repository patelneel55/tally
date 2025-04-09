from enum import Enum


class OpenAIModels(str, Enum):
    """
    Enum for OpenAI models.
    """

    GPT_4O = "gpt-4o"
    GPT_O3_MINI = "gpt-4-turbo"
