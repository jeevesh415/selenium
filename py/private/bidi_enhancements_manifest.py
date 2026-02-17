"""
Enhancement manifest for BiDi code generation.

This file defines custom enhancements applied to generated BiDi modules,
including custom dataclass methods, parameter validation/transformation,
response deserialization, and field extraction.

All code must be compatible with Python 3.10+.
"""

from __future__ import annotations

from typing import Any

# ============================================================================
# Format Guide
# ============================================================================
# Each module in ENHANCEMENTS specifies enhancement rules for methods:
#
# 'module_name': {
#     'method_name': {
#         'dataclass_methods': {   # For dataclass enhancements
#             'ClassName': ['method1', 'method2', ...]
#         },
#         'preprocess': {          # Pre-processing on parameters
#             'param_name': 'check_serialize_method'
#         },
#         'deserialize': {         # Deserialize response to typed objects
#             'response_field': 'TypeName',
#         },
#         'extract_field': str,    # Extract nested field from response
#         'extract_property': str, # Extract property from extracted items
#         'validate': str,         # Validation function name
#         'transform': str,        # Transformation function name
#     }
# }
# ============================================================================

ENHANCEMENTS: dict[str, dict[str, dict[str, Any]]] = {
    "browser": {
        # Dataclass custom methods
        "__dataclass_methods__": {
            "ClientWindowInfo": [
                "get_client_window",
                "get_state",
                "get_width",
                "get_height",
                "is_active",
                "get_x",
                "get_y",
            ],
        },
        # Method enhancements
        "create_user_context": {
            "preprocess": {
                "proxy": "check_serialize_method",
            },
            "extract_field": "userContext",
        },
        "get_client_windows": {
            "deserialize": {
                "clientWindows": "ClientWindowInfo",
            },
        },
        "get_user_contexts": {
            "extract_field": "userContexts",
            "extract_property": "userContext",
        },
        # Note: set_download_behavior requires method signature transformation
        # which is handled separately - not yet implemented in the generator
    },
    "browsingContext": {
        # Method enhancements
        "create": {
            "extract_field": "context",
        },
    },
}


# ============================================================================
# Pre-processing Functions
# ============================================================================


def check_serialize_method(obj: Any) -> Any:
    """Check if object has to_bidi_dict() method and use it for serialization."""
    if obj and hasattr(obj, "to_bidi_dict"):
        return obj.to_bidi_dict()
    return obj


# ============================================================================
# Validation Functions
# ============================================================================


def validate_download_behavior(
    allowed: bool | None,
    destination_folder: str | None,
) -> None:
    """Validate download behavior parameters.

    Args:
        allowed: Whether downloads are allowed
        destination_folder: Destination folder for downloads

    Raises:
        ValueError: If parameters are invalid
    """
    if allowed is True and not destination_folder:
        raise ValueError("destination_folder is required when allowed=True")
    if allowed is False and destination_folder:
        raise ValueError("destination_folder should not be provided when allowed=False")


# ============================================================================
# Transformation Functions
# ============================================================================


def transform_download_params(
    allowed: bool | None,
    destination_folder: str | None,
) -> dict[str, Any]:
    """Transform download parameters into download_behavior object.

    Args:
        allowed: Whether downloads are allowed
        destination_folder: Destination folder for downloads

    Returns:
        Dictionary representing the download_behavior object, or None if allowed is None
    """
    if allowed is True:
        return {
            "type": "allowed",
            "destinationFolder": destination_folder,
        }
    elif allowed is False:
        return {"type": "denied"}
    else:  # None - don't send any download_behavior
        return None


# ============================================================================
# Dataclass Method Templates
# ============================================================================

DATACLASS_METHOD_TEMPLATES: dict[str, dict[str, str]] = {
    "ClientWindowInfo": {
        "get_client_window": "return self.client_window",
        "get_state": "return self.state",
        "get_width": "return self.width",
        "get_height": "return self.height",
        "is_active": "return self.active",
        "get_x": "return self.x",
        "get_y": "return self.y",
    },
}

DATACLASS_METHOD_DOCSTRINGS: dict[str, dict[str, str]] = {
    "ClientWindowInfo": {
        "get_client_window": "Get the client window ID.",
        "get_state": "Get the client window state.",
        "get_width": "Get the client window width.",
        "get_height": "Get the client window height.",
        "is_active": "Check if the client window is active.",
        "get_x": "Get the client window X position.",
        "get_y": "Get the client window Y position.",
    },
}
