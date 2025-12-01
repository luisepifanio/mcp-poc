from abc import ABC, abstractmethod
from typing import TypeVar

# Definir tipos genéricos para Input y Output
InputPort = TypeVar("InputPort")
OutputPort = TypeVar("OutputPort")


class UseCase[InputPort, OutputPort](ABC):
    """Abstracción base para use cases síncronos."""

    @abstractmethod
    def execute(self, input: InputPort) -> OutputPort:
        """Ejecuta la lógica del use case."""
        pass


class AsyncUseCase[InputPort, OutputPort](ABC):
    """Abstracción base para use cases asíncronos."""

    @abstractmethod
    async def execute(self, input: InputPort) -> OutputPort:
        """Ejecuta la lógica del use case de forma asíncrona."""
        pass
