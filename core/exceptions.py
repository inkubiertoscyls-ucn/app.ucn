"""Custom exceptions for INKubiertos backend."""


class INKubiertosException(Exception):
    """Base exception for INKubiertos."""
    pass


class ValidationError(INKubiertosException):
    """Validation error."""
    pass


class AuthenticationError(INKubiertosException):
    """Authentication error."""
    pass


class AuthorizationError(INKubiertosException):
    """Authorization/permission error."""
    pass


class NotFoundError(INKubiertosException):
    """Resource not found."""
    pass


class InventoryError(INKubiertosException):
    """Inventory operation error."""
    pass


class NegativeStockError(InventoryError):
    """Stock would become negative."""
    pass


class DuplicateError(INKubiertosException):
    """Duplicate resource."""
    pass


class InvalidRUTError(ValidationError):
    """Invalid Chilean RUT."""
    pass


class SupabaseConnectionError(INKubiertosException):
    """Supabase connection error."""
    pass
