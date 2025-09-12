# Modular Logistics Agent Architecture

## Overview

The logistics agent has been refactored to use a modular approach with LLM-based parsing and organized tool structure. This design provides better maintainability, reusability, and separation of concerns.

## Architecture

### 1. Main Agent (`agent.py`)
- **Single entry point** for the logistics system
- Uses `create_react_agent` with modular tools
- Handles natural language processing and tool orchestration
- Provides clear user feedback and confirmations

### 2. Tools Directory (`tools/`)

#### `tools/llm_parser.py`
- **LLM-based parsing** using a single model instance
- Pydantic schemas for data validation
- Fallback regex parsing for reliability
- Handles: Owner, Driver, Vehicle, Trip, and Expense parsing

#### `tools/parsing_tools.py`
- **Clean interface** for parsing functions
- Wraps LLM parser with simple function calls
- Easy to import and use across the system

#### `tools/database_tools.py`
- **Database operations** using SQLAlchemy
- CRUD operations for all entities
- Comprehensive error handling
- Query functions for reporting

#### `tools/__init__.py`
- **Centralized imports** for all tools
- Clean API for external usage
- Organized exports

## Key Features

### 🧠 LLM-Based Parsing
- Uses a single LLM instance for consistent parsing
- Pydantic schemas ensure data validation
- Fallback mechanisms for reliability
- Natural language to structured data conversion

### 🔧 Modular Tools
- Each tool has a single responsibility
- Easy to test and maintain
- Reusable across different contexts
- Clear separation of concerns

### 🗄️ Database Operations
- SQLAlchemy ORM for database management
- Comprehensive CRUD operations
- Error handling and rollback support
- Query functions for reporting

### 📊 Agent Capabilities
1. **Owner Management**: Register and manage vehicle owners
2. **Driver Management**: Register and manage drivers
3. **Vehicle Management**: Add and track vehicles
4. **Trip Management**: Create and manage trips
5. **Expense Tracking**: Record and track expenses
6. **Reporting**: Generate summaries and reports

## Usage Examples

### Natural Language Inputs
```python
# Owner registration
"I am John Doe, phone 9876543210, email john@example.com"

# Driver registration
"Register driver Mike Smith with license DL1234567890"

# Vehicle addition
"Add vehicle KA01AB1234 for owner 1"

# Expense recording
"Record expense of ₹500 for fuel on trip 1"

# Queries
"Show me summary for owner 1"
"What are the expenses for vehicle 1?"
```

### Tool Workflow
1. **Parse** → Extract structured data from natural language
2. **Process** → Perform database operations
3. **Confirm** → Provide user feedback

## Benefits

### ✅ Maintainability
- Clear separation of concerns
- Easy to modify individual components
- Centralized configuration

### ✅ Reusability
- Tools can be used independently
- Easy to add new functionality
- Consistent API across tools

### ✅ Reliability
- Fallback parsing mechanisms
- Comprehensive error handling
- Data validation with Pydantic

### ✅ Scalability
- Easy to add new entity types
- Modular tool structure
- LLM-based parsing scales with model improvements

## File Structure

```
├── agent.py                 # Main agent entry point
├── tools/
│   ├── __init__.py         # Tool exports
│   ├── llm_parser.py       # LLM-based parsing
│   ├── parsing_tools.py    # Parsing interface
│   └── database_tools.py   # Database operations
├── langgraph.json          # LangGraph configuration
└── test_agent.py           # Test script
```

## Configuration

The agent uses the `DEFAULT_MODEL` from the `llms` module and is configured through `langgraph.json` to point to the main agent function.

## Testing

Run the test script to see the agent in action:
```bash
python test_agent.py
```

This modular architecture provides a solid foundation for the logistics management system with room for future enhancements and easy maintenance.
