"""
Logistics Agent - Main entry point for the logistics management system.
Uses modular tools and LLM-based parsing for natural language processing.
"""

from llms import DEFAULT_MODEL
from langgraph.prebuilt import create_react_agent
from typing import Dict, Any
from langchain_core.tools import tool

# Import modular tools
from tools import (
    parse_owner_nl,
    parse_driver_nl,
    parse_vehicle_nl,
    parse_trip_nl,
    parse_expense_nl,
    register_owner,
    register_driver,
    add_vehicle,
    add_trip,
    add_expense,
    
    get_owner_summary,
    get_vehicle_expenses,
    get_trip_details,
    get_driver_expenses
)


# Create LangChain tools from our functions
@tool
def parse_owner_tool(text: str) -> Dict[str, Any]:
    """Parse owner registration information from natural language."""
    return parse_owner_nl(text)


@tool
def parse_driver_tool(text: str) -> Dict[str, Any]:
    """Parse driver registration information from natural language."""
    return parse_driver_nl(text)


@tool
def parse_vehicle_tool(text: str) -> Dict[str, Any]:
    """Parse vehicle registration information from natural language."""
    return parse_vehicle_nl(text)


@tool
def parse_trip_tool(text: str) -> Dict[str, Any]:
    """Parse trip information from natural language."""
    return parse_trip_nl(text)


@tool
def parse_expense_tool(text: str) -> Dict[str, Any]:
    """Parse expense information from natural language."""
    return parse_expense_nl(text)


@tool
def register_owner_tool(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Register a new owner in the database."""
    return register_owner(parsed_data)


@tool
def register_driver_tool(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Register a new driver in the database."""
    return register_driver(parsed_data)


@tool
def add_vehicle_tool(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new vehicle to the database."""
    return add_vehicle(parsed_data)


@tool
def add_trip_tool(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new trip to the database."""
    return add_trip(parsed_data)


@tool
def add_expense_tool(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new expense to the database."""
    return add_expense(parsed_data)


@tool
def get_owner_summary_tool(owner_id: int) -> Dict[str, Any]:
    """Get summary information for an owner."""
    return get_owner_summary(owner_id)


@tool
def get_vehicle_expenses_tool(vehicle_id: int) -> Dict[str, Any]:
    """Get expense summary for a vehicle."""
    return get_vehicle_expenses(vehicle_id)


@tool
def get_trip_details_tool(trip_id: int) -> Dict[str, Any]:
    """Get detailed information for a trip."""
    return get_trip_details(trip_id)


@tool
def get_driver_expenses_tool(driver_id: int) -> Dict[str, Any]:
    """Get expense summary for a driver."""
    return get_driver_expenses(driver_id)


def create_logistics_agent():
    """Create the main logistics agent with all tools."""
    
    # Create the main logistics agent
    agent = create_react_agent(
        model=DEFAULT_MODEL,
        tools=[
            # Parsing tools
            parse_owner_tool, parse_driver_tool, parse_vehicle_tool, parse_trip_tool, parse_expense_tool,
            # Registration tools
            register_owner_tool, register_driver_tool, add_vehicle_tool, add_trip_tool, add_expense_tool,
            # Query tools
            get_owner_summary_tool, get_vehicle_expenses_tool, get_trip_details_tool, get_driver_expenses_tool
        ]
    )
    
    return agent


# Create the main agent
main_agent = create_logistics_agent()



