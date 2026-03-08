"""Base stage runner interface.

All pipeline stages must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
from pydantic import BaseModel


class StageRunner(ABC):
    """Abstract base class for pipeline stages.
    
    Each stage:
    1. Validates input
    2. Executes deterministic logic
    3. Returns validated output
    4. Supports semantic validation
    """
    
    @property
    @abstractmethod
    def stage_name(self) -> str:
        """Unique stage identifier."""
        pass
    
    @property
    @abstractmethod
    def input_model(self) -> type[BaseModel]:
        """Pydantic model for input validation."""
        pass
    
    @property
    @abstractmethod
    def output_model(self) -> type[BaseModel]:
        """Pydantic model for output validation."""
        pass
    
    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the stage logic.
        
        Args:
            input_data: Validated input data
        
        Returns:
            Output data (will be validated against output_model)
        """
        pass
    
    def validate_semantic(self, output: BaseModel) -> Tuple[bool, str]:
        """Semantic validation beyond JSON schema.
        
        Args:
            output: Validated output model
        
        Returns:
            (is_valid, error_message)
        
        Override this method to add custom semantic validation rules.
        """
        return True, ""
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run the complete stage pipeline.
        
        1. Validate input
        2. Execute logic
        3. Validate output (JSON + semantic)
        
        Args:
            input_data: Raw input data
        
        Returns:
            Validated output data
        
        Raises:
            ValueError: If validation fails
        """
        # Validate input
        try:
            validated_input = self.input_model(**input_data)
        except Exception as e:
            raise ValueError(f"Input validation failed: {e}")
        
        # Execute
        output_data = self.execute(validated_input.model_dump())
        
        # Validate output (JSON schema)
        try:
            validated_output = self.output_model(**output_data)
        except Exception as e:
            raise ValueError(f"Output validation failed: {e}")
        
        # Semantic validation
        is_valid, error_msg = self.validate_semantic(validated_output)
        if not is_valid:
            raise ValueError(f"Semantic validation failed: {error_msg}")
        
        return validated_output.model_dump()
