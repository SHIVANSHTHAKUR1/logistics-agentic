"""
Parsing tools that use LLM for natural language processing.
These tools provide a clean interface for parsing different types of data.
"""

from typing import Dict, Any
from .llm_parser import get_parser


def parse_owner_nl(text: str) -> Dict[str, Any]:
    """Parse owner registration information from natural language."""
    parser = get_parser()
    return parser.parse_owner(text)


def parse_driver_nl(text: str) -> Dict[str, Any]:
    """Parse driver registration information from natural language."""
    parser = get_parser()
    return parser.parse_driver(text)


def parse_vehicle_nl(text: str) -> Dict[str, Any]:
    """Parse vehicle registration information from natural language."""
    parser = get_parser()
    return parser.parse_vehicle(text)


def parse_trip_nl(text: str) -> Dict[str, Any]:
    """Parse trip information from natural language."""
    parser = get_parser()
    return parser.parse_trip(text)


def parse_expense_nl(text: str) -> Dict[str, Any]:
    """Parse expense information from natural language."""
    parser = get_parser()
    return parser.parse_expense(text)
