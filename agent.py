"""
Logistics Agent - Main entry point for the logistics management system.
Uses modular tools and LLM-based parsing for natural language processing.
"""

from llms import DEFAULT_MODEL
from typing import Dict, Any, List
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from typing_extensions import TypedDict

# Import modular tools
from tools import (
    parse_owner_nl,
    parse_driver_nl,
    parse_user_nl,
    parse_vehicle_nl,
    parse_trip_nl,
    parse_expense_nl,
    register_owner,
    register_user,
    add_vehicle,
    add_trip,
    add_expense,
    create_load,
    assign_load_to_trip,
    add_location_update,
    get_owner_summary,
    get_vehicle_summary,
    get_trip_details,
    get_user_expenses,
    get_load_details
)


# Create LangChain tools from our functions
@tool
def parse_owner_tool(text: str) -> Dict[str, Any]:
    """Parse owner/company registration information from natural language. Use this FIRST before registering an owner. 
    Extracts: company_name, business_address, contact_email, gst_number from text like 
    'Register ABC Logistics company at 123 Main St, contact abc@logistics.com, GST: 12ABCDE3456F7Z8'."""
    return parse_owner_nl(text)


@tool
def parse_driver_tool(text: str) -> Dict[str, Any]:
    """Parse driver registration information from natural language. Use this FIRST before registering a driver.
    Extracts: name, phone, license_no from text like 'I am John Doe, phone 9876543210, license DL1234567890'.
    Note: This creates driver data that will be converted to user format with role='driver'."""
    return parse_driver_nl(text)


@tool
def parse_customer_tool(text: str) -> Dict[str, Any]:
    """Parse customer registration information from natural language. Use this FIRST before registering a customer.
    Extracts: full_name, email, phone_number, address from text like 'Customer John Doe, email john@example.com, phone 9876543210, address Mumbai'.
    Note: This creates user data with role='customer'."""
    return parse_user_nl(text)


@tool
def parse_vehicle_tool(text: str) -> Dict[str, Any]:
    """Parse vehicle registration information from natural language.
    Extracts: license_plate, capacity_kg, status from text like 'Register truck MH01AB1234 with 10000kg capacity'."""
    return parse_vehicle_nl(text)


@tool
def parse_trip_tool(text: str) -> Dict[str, Any]:
    """Parse trip information from natural language.
    Extracts: driver_id, vehicle_id, status from text like 'Create trip with driver 1 using vehicle 2'."""
    return parse_trip_nl(text)


@tool
def parse_expense_tool(text: str) -> Dict[str, Any]:
    """Parse expense information from natural language.
    Extracts: driver_id, expense_type, amount, trip_id (optional), description, receipt_url from text like 
    'Driver 1 spent Rs.500 on fuel for trip 2'."""
    return parse_expense_nl(text)


@tool
def register_owner_tool(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Register a new owner/company in the database. Use this AFTER parsing owner information.
    Required fields: company_name, business_address, contact_email
    Optional fields: gst_number
    Takes parsed data from parse_owner_tool and creates an owner/company record."""
    return register_owner(parsed_data)


@tool
def register_user_tool(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Register a new user in the database. Use this AFTER parsing user information.
    Required fields: owner_id, full_name, email, password_hash, phone_number, role
    Role must be one of: customer, driver, owner
    Takes parsed data and creates a user record associated with a company."""
    return register_user(parsed_data)


@tool
def register_driver_tool(input_data) -> Dict[str, Any]:
    """Register a new driver in the database. Input can be either:
    1. Parsed data dict from parse_driver_tool (preferred)
    2. Raw text that will be automatically parsed
    
    Creates a driver user record with role='driver'. Email is required."""
    
    # Handle different input types
    if isinstance(input_data, str):
        # If string provided, parse it first
        parsed_data = parse_driver_nl(input_data)
        if parsed_data.get('status') == 'error':
            return parsed_data  # Return parsing error
    elif isinstance(input_data, dict):
        parsed_data = input_data
    else:
        return {"status": "error", "message": "Invalid input type. Expected dict or string."}
    
    # Check if email is provided and valid
    email = parsed_data.get('email')
    if not email or not email.strip() or '@' not in email:
        driver_name = parsed_data.get('name', 'the driver')
        return {
            "status": "incomplete", 
            "message": f"I need an email address for {driver_name} to complete the registration. Please provide the email and try again.",
            "missing_field": "email",
            "driver_data": parsed_data
        }
    
    # Convert driver format to user format
    user_data = {
        'full_name': parsed_data.get('name', 'Unknown Driver'),
        'email': email.strip(),
        'password_hash': 'temp_hash_' + str(hash(parsed_data.get('name', 'temp'))),
        'phone_number': parsed_data.get('phone', '0000000000'),
        'role': 'driver',
        'owner_id': parsed_data.get('owner_id', 1)  # Default to owner_id 1 for backward compatibility
    }
    return register_user(user_data)


@tool
def register_customer_tool(input_data) -> Dict[str, Any]:
    """Register a new customer in the database. Input can be either:
    1. Parsed data dict from parse_customer_tool (preferred)
    2. Raw text that will be automatically parsed
    
    Creates a customer user record with role='customer'. Email is required."""
    
    # Handle different input types
    if isinstance(input_data, str):
        # If string provided, parse it first
        parsed_data = parse_user_nl(input_data)
        if parsed_data.get('status') == 'error':
            return parsed_data  # Return parsing error
    elif isinstance(input_data, dict):
        parsed_data = input_data
    else:
        return {"status": "error", "message": "Invalid input type. Expected dict or string."}
    
    # Check if email is provided and valid
    email = parsed_data.get('email')
    if not email or not email.strip() or '@' not in email:
        customer_name = parsed_data.get('full_name', 'the customer')
        return {
            "status": "incomplete", 
            "message": f"I need an email address for {customer_name} to complete the registration. Please provide the email and try again.",
            "missing_field": "email",
            "customer_data": parsed_data
        }
    
    # Ensure role is set to customer
    user_data = {
        'full_name': parsed_data.get('full_name', 'Unknown Customer'),
        'email': email.strip(),
        'password_hash': 'temp_hash_' + str(hash(parsed_data.get('full_name', 'temp'))),
        'phone_number': parsed_data.get('phone_number', '0000000000'),
        'role': 'customer',
        'owner_id': parsed_data.get('owner_id', 1)  # Default to owner_id 1 for backward compatibility
    }
    return register_user(user_data)


@tool
def complete_driver_registration_tool(email: str) -> Dict[str, Any]:
    """Complete driver registration when email is provided after initial attempt.
    Note: With the simplified approach, please provide all driver information again with email included."""
    
    return {
        "status": "info",
        "message": "Please provide the driver registration information again including the email address. Use register_driver_tool with all details."
    }


@tool
def add_vehicle_tool(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new vehicle to the database.
    Required fields: owner_id, license_plate, capacity_kg
    Optional fields: status (available, in_use, maintenance, out_of_service)
    The vehicle will be associated with the specified owner/company."""
    return add_vehicle(parsed_data)


@tool
def add_trip_tool(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new trip to the database.
    Required fields: driver_id, vehicle_id
    Optional fields: status (scheduled, in_progress, completed, cancelled), start_time, end_time
    The driver must have role='driver' and both driver and vehicle must exist."""
    return add_trip(parsed_data)


@tool
def add_expense_tool(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new expense to the database.
    Required fields: driver_id, expense_type, amount
    Optional fields: trip_id, description, receipt_url
    Expense type must be one of: fuel, maintenance, toll, food, accommodation, other
    Amount must be greater than 0."""
    return add_expense(parsed_data)


@tool
def create_load_tool(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new load request in the database.
    Required fields: customer_id, pickup_address, destination_address
    Optional fields: weight_kg, description, status (pending, assigned, in_transit, delivered, cancelled)
    The customer must have role='customer'."""
    return create_load(parsed_data)


@tool
def assign_load_to_trip_tool(load_id: int, trip_id: int) -> Dict[str, Any]:
    """Assign a load to a trip."""
    return assign_load_to_trip(load_id, trip_id)


@tool
def add_location_update_tool(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a location update for a trip.
    Required fields: trip_id, latitude, longitude
    Optional fields: speed_kmh, address
    The trip must exist and be in progress for location tracking."""
    return add_location_update(parsed_data)


@tool
def get_owner_summary_tool(owner_id) -> Dict[str, Any]:
    """Get summary information for an owner. 
    
    Args:
        owner_id: The ID of the owner (can be string or number, e.g., 1, "1", "5")
    
    Example: For "owner ID 5", pass owner_id=5 or owner_id="5" """
    # Convert string to int if needed
    if isinstance(owner_id, str):
        owner_id = int(owner_id)
    return get_owner_summary(owner_id)


@tool
def get_vehicle_summary_tool(vehicle_id) -> Dict[str, Any]:
    """Get summary information for a vehicle.
    
    Args:
        vehicle_id: The ID of the vehicle (can be string or number, e.g., 1, "1", "5")
    
    Example: For "vehicle ID 5", pass vehicle_id=5 or vehicle_id="5" """
    # Convert string to int if needed
    if isinstance(vehicle_id, str):
        vehicle_id = int(vehicle_id)
    return get_vehicle_summary(vehicle_id)


@tool
def get_vehicle_expenses_tool(vehicle_id: int) -> Dict[str, Any]:
    """Get expense summary for a vehicle (backward compatibility)."""
    return get_vehicle_summary(vehicle_id)


@tool
def get_trip_details_tool(trip_id) -> Dict[str, Any]:
    """Get detailed information for a trip.
    
    Args:
        trip_id: The ID of the trip (can be string or number, e.g., 1, "1", "5")
    
    Example: For "trip ID 5", pass trip_id=5 or trip_id="5" """
    # Convert string to int if needed
    if isinstance(trip_id, str):
        trip_id = int(trip_id)
    return get_trip_details(trip_id)


@tool
def get_user_expenses_tool(user_id) -> Dict[str, Any]:
    """Get expense summary for a user.
    
    Args:
        user_id: The ID of the user (can be string or number, e.g., 1, "1", "5")
    
    Example: For "user ID 5", pass user_id=5 or user_id="5" """
    # Convert string to int if needed
    if isinstance(user_id, str):
        user_id = int(user_id)
    return get_user_expenses(user_id)


@tool
def get_driver_expenses_tool(driver_id) -> Dict[str, Any]:
    """Get expense summary for a driver.
    
    Args:
        driver_id: The ID of the driver (can be string or number, e.g., 1, "1", "5")
    
    Example: For "driver ID 5", pass driver_id=5 or driver_id="5" """
    # Convert string to int if needed
    if isinstance(driver_id, str):
        driver_id = int(driver_id)
    return get_user_expenses(driver_id)


@tool
def get_load_details_tool(load_id) -> Dict[str, Any]:
    """Get detailed information for a load.
    
    Args:
        load_id: The ID of the load (can be string or number, e.g., 1, "1", "5")
    
    Example: For "load ID 5", pass load_id=5 or load_id="5" """
    # Convert string to int if needed
    if isinstance(load_id, str):
        load_id = int(load_id)
    return get_load_details(load_id)


# Define the state for our LangGraph
class LogisticsState(TypedDict):
    """State for the logistics agent."""
    messages: List[Any]
    user_input: str
    next_action: str  # Added to control flow


def create_logistics_graph():
    """Create a LangGraph StateGraph for the logistics agent."""
    
    # Create the tools dictionary
    tools = {
        # Parsing tools
        "parse_owner_tool": parse_owner_tool,
        "parse_driver_tool": parse_driver_tool,
        "parse_customer_tool": parse_customer_tool,
        "parse_vehicle_tool": parse_vehicle_tool,
        "parse_trip_tool": parse_trip_tool,
        "parse_expense_tool": parse_expense_tool,
        # Registration tools
        "register_owner_tool": register_owner_tool,
        "register_user_tool": register_user_tool,
        "register_driver_tool": register_driver_tool,
        "register_customer_tool": register_customer_tool,
        "complete_driver_registration_tool": complete_driver_registration_tool,
        "add_vehicle_tool": add_vehicle_tool,
        "add_trip_tool": add_trip_tool,
        "add_expense_tool": add_expense_tool,
        # Load management tools
        "create_load_tool": create_load_tool,
        "assign_load_to_trip_tool": assign_load_to_trip_tool,
        # Location tracking tools
        "add_location_update_tool": add_location_update_tool,
        # Query tools
        "get_owner_summary_tool": get_owner_summary_tool,
        "get_vehicle_summary_tool": get_vehicle_summary_tool,
        "get_vehicle_expenses_tool": get_vehicle_expenses_tool,
        "get_trip_details_tool": get_trip_details_tool,
        "get_user_expenses_tool": get_user_expenses_tool,
        "get_driver_expenses_tool": get_driver_expenses_tool,
        "get_load_details_tool": get_load_details_tool
    }
    
    # Create model with all tools
    model = DEFAULT_MODEL.bind_tools(list(tools.values()))
    
    def agent_node(state: LogisticsState) -> LogisticsState:
        """Agent node that decides what to do next."""
        user_input = state.get("user_input", "")
        messages = state.get("messages", [])
        
        # If no messages yet, start with user input and add system prompt
        if not messages and user_input:
            system_prompt = """You are an autonomous Logistics Management Agent. Your goal is to COMPLETE tasks fully using available tools.

AUTONOMOUS WORKFLOW:
1. Analyze the human's request thoroughly
2. Use appropriate tools to gather information or perform actions
3. If a tool returns an error or incomplete result, use OTHER tools or approaches to resolve it
4. Continue working until the task is FULLY COMPLETED
5. Only stop when you have successfully completed the user's request OR need critical information that only the human can provide

AVAILABLE OPERATIONS:
- PARSING: parse_owner_tool, parse_driver_tool, parse_customer_tool, parse_vehicle_tool, parse_trip_tool, parse_expense_tool
- REGISTRATION: register_owner_tool, register_driver_tool, register_customer_tool, add_vehicle_tool, add_trip_tool, add_expense_tool
- LOAD MANAGEMENT: create_load_tool, assign_load_to_trip_tool
- TRACKING: add_location_update_tool
- QUERIES: get_owner_summary_tool, get_vehicle_summary_tool, get_trip_details_tool, get_load_details_tool, get_driver_expenses_tool

CRITICAL RULES:
- NEVER give up after one failed attempt - try alternative approaches
- If parsing fails, try the registration tool directly (it has auto-parsing)
- If register_driver_tool or register_customer_tool returns status='incomplete' asking for email, STOP and ask the human for the email
- If you need an ID (like owner_id), make reasonable assumptions (default to 1) or query existing records first
- For numeric IDs in queries, extract just the number (e.g., "owner ID 5" → 5)
- Keep working until the task is 100% complete
- If you complete a task successfully, provide a clear summary of what was accomplished

DRIVER REGISTRATION WORKFLOW:
- If driver registration is missing email, the tool will return status='incomplete'
- When this happens, ask the human to provide the email address and try the registration again with all information

CUSTOMER REGISTRATION WORKFLOW:
- If customer registration is missing email, the tool will return status='incomplete'
- When this happens, ask the human to provide the email address and try the registration again with all information
- Email is required for all driver and customer registrations

EXAMPLE FLOWS:
Scenario 1: Driver registration without email
User: "Add driver John Doe with license DL123"
1. Try register_driver_tool directly
2. If tool returns status='incomplete' asking for email, ask human for email
3. When user provides email, ask them to provide all driver information again including email

Scenario 2: Complete driver registration
User: "Add driver John Doe, license DL123, email john@email.com"
1. Try register_driver_tool with all information
2. Should complete successfully

Scenario 3: Customer registration without email
User: "Add customer Jane Smith, phone 9876543210, address Mumbai"
1. Try register_customer_tool directly
2. If tool returns status='incomplete' asking for email, ask human for email
3. When user provides email, try register_customer_tool again with all information including email

Scenario 4: Complete customer registration with email provided later
User first says: "name is customer1, address is rajpura, phone number is +91 8346467372"
Agent asks for email, user then says: "email address is customer1@gmail.com"
Agent should: Try register_customer_tool with ALL information: "customer1, rajpura, +91 8346467372, customer1@gmail.com"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_input)
            ]
        
        # Get model response
        try:
            response = model.invoke(messages)
            messages.append(response)
            
            # Check if model made tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                # Model wants to use tools
                next_action = "tools"
            else:
                # Model provided final response
                next_action = "end"
                
        except Exception as e:
            # Error in model invocation
            error_response = AIMessage(content=f"Error: {str(e)}")
            messages.append(error_response)
            next_action = "end"
        
        return {
            "messages": messages, 
            "user_input": user_input,
            "next_action": next_action
        }
    
    def tools_node(state: LogisticsState) -> LogisticsState:
        """Tools node that executes tool calls and returns to agent."""
        messages = state.get("messages", [])
        user_input = state.get("user_input", "")
        
        # Get the last message which should contain tool calls
        last_message = messages[-1] if messages else None
        
        if last_message and hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            # Execute each tool call
            for tool_call in last_message.tool_calls:
                tool_name = tool_call['name']
                tool_args = tool_call['args']
                tool_id = tool_call['id']
                
                if tool_name in tools:
                    try:
                        # Execute the tool
                        tool_result = tools[tool_name].invoke(tool_args)
                        
                        # Add tool result to messages
                        tool_message = ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_id
                        )
                        messages.append(tool_message)
                        
                    except Exception as e:
                        # Add error message
                        error_message = ToolMessage(
                            content=f"Error executing {tool_name}: {str(e)}",
                            tool_call_id=tool_id
                        )
                        messages.append(error_message)
                else:
                    # Unknown tool
                    error_message = ToolMessage(
                        content=f"Unknown tool: {tool_name}",
                        tool_call_id=tool_id
                    )
                    messages.append(error_message)
        
        # After executing tools, go back to agent
        return {
            "messages": messages, 
            "user_input": user_input,
            "next_action": "agent"
        }
    
    def should_continue(state: LogisticsState) -> str:
        """Decide what to do next based on the state."""
        next_action = state.get("next_action", "end")
        return next_action
    
    # Create the graph
    workflow = StateGraph(LogisticsState)
    
    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tools_node)
    
    # Set the entry point
    workflow.add_edge(START, "agent")
    
    # Add conditional edges based on next_action
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )
    
    # Tools always go back to agent
    workflow.add_edge("tools", "agent")
    
    # Compile the graph
    return workflow.compile()


# Create the main agent (LangGraph compatible)
main_agent = create_logistics_graph()



