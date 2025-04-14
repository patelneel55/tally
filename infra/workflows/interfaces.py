from abc import ABC, abstractmethod
from typing import Any

class IWorkflow(ABC):
    """
    Interface for workflows that can predefine set of steps
    to execute and satisfy a CUJ
    """

    @abstractmethod
    async def run(self) -> Any:
        """
        Build and execute the workflow

        The workflow will execute the predefined steps as part
        of its LangGraph structure
        """
