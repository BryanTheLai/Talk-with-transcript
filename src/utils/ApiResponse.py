from typing import Any, Dict, Optional, TypeVar, Generic, List

T = TypeVar('T')

class ApiResponse(Generic[T]):
    """Standard response wrapper for all API operations"""
    def __init__(
        self, 
        success: bool, 
        data: Optional[T] = None,
        error: Optional[str] = None,
        error_code: Optional[str] = None
    ):
        self.success = success
        self.data = data
        self.error = error
        self.error_code = error_code
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary"""
        result = {"success": self.success}
        if self.data is not None:
            result["data"] = self.data
        if self.error is not None:
            result["error"] = self.error
        if self.error_code is not None:
            result["error_code"] = self.error_code
        return result