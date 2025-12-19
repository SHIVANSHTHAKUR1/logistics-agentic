#!/usr/bin/env python3
"""
Flask web application for logistics chat interface
Integrates with the modular LangGraph agent (Router → Query → Verify → Reflect → End).
The agent is invoked in-process via agent.main_agent and returns a state dict with messages.
"""

from flask import Flask, render_template, request, jsonify, session
import json
import traceback
from datetime import datetime
import uuid

# Import the basic functions directly
try:
    from tools.database_tools import *
    from tools.parsing_tools import *
    TOOLS_AVAILABLE = True
    
    # Import the actual agent
    try:
        from agent import main_agent
        AGENT_AVAILABLE = True
        print("✓ LangGraph agent loaded successfully")
    except Exception as e:
        AGENT_AVAILABLE = False
        print(f"⚠️ Agent not available: {e}")
    
    # Test if LLM parsing is working
    try:
        from tools.llm_parser import LLMParser
        test_parser = LLMParser()
        if test_parser.model is not None:
            LLM_AVAILABLE = True
        else:
            LLM_AVAILABLE = False
            print("⚠️ LLM model not available, using pattern matching only")
    except Exception as e:
        LLM_AVAILABLE = False
        print(f"⚠️ LLM parser not available: {e}")
        
except Exception as e:
    print(f"Warning: Could not import tools: {e}")
    TOOLS_AVAILABLE = False
    LLM_AVAILABLE = False
    AGENT_AVAILABLE = False

app = Flask(__name__)
app.secret_key = 'logistics_secret_key_' + str(uuid.uuid4())

# Store conversation histories (in production, use Redis or database)
conversation_histories = {}


ALLOWED_ROLES = {"customer", "driver", "owner"}


def _normalize_role(role: str) -> str:
    r = (role or "").strip().lower()
    return r if r in ALLOWED_ROLES else "owner"


def _set_session_role(new_role: str) -> None:
    """Set session role; if changed, clear per-session conversation and entities."""
    new_role = _normalize_role(new_role)
    prev_role = _normalize_role(session.get("role", "owner"))
    if prev_role != new_role:
        # Role change implies new permissions/context; clear continuity state.
        session["role"] = new_role
        session.pop("entities", None)
        sid = session.get("session_id")
        if sid and sid in conversation_histories:
            del conversation_histories[sid]
    else:
        session["role"] = new_role

def get_conversation_history(session_id: str) -> list:
    """Get conversation history for a session."""
    return conversation_histories.get(session_id, [])

def update_conversation_history(session_id: str, messages: list):
    """Update conversation history for a session."""
    conversation_histories[session_id] = messages

def process_logistics_request(user_input: str, session_id: str = None, actor_role: str = "owner") -> dict:
    """Process logistics requests using the intelligent agent."""
    try:
        start_time = datetime.now()
        
        if not TOOLS_AVAILABLE:
            return {
                "success": False,
                "response": "Tools not available. Please ensure database tools are properly installed.",
                "response_time": 0,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
        
        # Use the intelligent agent if available
        if AGENT_AVAILABLE:
            try:
                # Get existing conversation history and session entities
                if session_id:
                    messages_history = get_conversation_history(session_id)
                    session_entities = session.get('entities', {}) or {}
                else:
                    messages_history = []
                    session_entities = {}
                
                # Invoke the LangGraph agent with conversation history and current user input
                # The modular graph routes based on user_input; next_action is inferred internally.
                # Invoke the LangGraph agent with conversation history, current user input, and prior entities
                result = main_agent.invoke({
                    "messages": messages_history,
                    "user_input": user_input,
                    "entities": session_entities,
                    "actor_role": actor_role,
                })
                
                # Extract the final response from messages and update conversation
                result_messages = result.get("messages", [])
                if result_messages:
                    # Update conversation history and merge entities into session state for multi-turn continuity
                    if session_id:
                        update_conversation_history(session_id, result_messages)
                        new_entities = result.get("entities", {}) or {}
                        if new_entities:
                            merged = dict(session_entities)
                            merged.update(new_entities)
                            session['entities'] = merged
                    
                    # Get the last meaningful AI text (skip tool messages if any)
                    response_text = None
                    for msg in reversed(result_messages):
                        content = getattr(msg, 'content', None)
                        # Tool messages may have tool_call_id attribute; prefer pure AI messages
                        if content and not getattr(msg, 'tool_call_id', None):
                            response_text = content
                            break
                    if not response_text:
                        response_text = "The agent processed your request but didn't provide a response."
                else:
                    response_text = "No response received from the agent."
                
                # Heuristic success: treat explicit failure phrases as unsuccessful
                lowered = response_text.lower()
                success = not ("no data" in lowered or "operation failed" in lowered or lowered.startswith("error:"))
                
            except Exception as e:
                response_text = f"Agent error: {str(e)}"
                success = False
                print(f"Agent execution error: {e}")
                traceback.print_exc()
        
        # Fallback to pattern matching if agent is not available
        else:
            response_text = """🚚 **Logistics Agent - Example Commands**

📝 **Registration & Setup:**
• "register user Raj Kumar with phone 9876543210 and email raj@example.com"
• "add owner ABC Logistics with email contact@abc.com"
• "register driver named Priya with license DL1234567890 phone 9988776655"
• "add vehicle MH12AB3456 with capacity 5000kg for owner 1"

🚛 **Trip Management:**
• "create trip with driver 1 and vehicle 2"
• "show trip 1 details" or just "trip 1"
• "show trip 1 expenses"
• "update trip 3 end time 2024-01-15 14:30"

📦 **Load Management:**
• "create load pickup Mumbai delivery Pune weight 1500kg description electronics"
• "assign load 2 to trip 1"
• "show load 3 details" or just "load 3"
• "update load 5 status delivered"

🚗 **Vehicle & Driver Queries:**
• "vehicle 2 summary" or "show vehicle MH01AB1234"
• "driver 1 summary"
• "update vehicle 3 status maintenance"
• "change driver 1 phone 9876543210"

💰 **Expenses & Tracking:**
• "add expense trip 1 fuel 500 description diesel"
• "driver 2 spent 300 on toll for trip 1"
• "show driver 1 expenses"
• After querying a trip: "total expenses" (shows trip expenses)

📍 **Location Updates:**
• "update location trip 1 at Mumbai"
• "add location for trip 2 lat 19.0760 lng 72.8777 address Andheri"

💡 **Tips:**
✓ Use natural language - the agent understands context
✓ IDs are automatically resolved from names, plates, or phone numbers
✓ The agent remembers conversation context
✓ Try "help" or ask anything about logistics!

⚠️ Note: Agent is currently unavailable. Please check configuration."""
            success = False

        end_time = datetime.now()
        response_time = (end_time - start_time).total_seconds()
        
        return {
            "success": success,
            "response": response_text,
            "response_time": response_time,
            "timestamp": end_time.strftime("%H:%M:%S")
        }
        
    except Exception as e:
        return {
            "success": False,
            "response": f"Error processing request: {str(e)}",
            "response_time": 0,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

@app.route('/')
def index():
    """Serve the main chat interface."""
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages."""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        actor_role = _normalize_role(data.get('role', session.get('role', 'owner')))

        # Ensure session exists and role is set early so help/examples reflect the current mode.
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        _set_session_role(actor_role)
        
        if not user_message:
            return jsonify({
                "success": False,
                "response": "Please enter a message."
            })
        
        # Handle special commands
        lower_msg = user_message.lower()
        if lower_msg in ['help', 'examples', 'example', 'show examples', 'what can you do']:
            examples_data = examples().get_json()
            
            response_parts = ["📚 **Available Commands by Category:**\n"]
            for category, cmds in examples_data['categories'].items():
                response_parts.append(f"\n**{category}:**")
                for cmd in cmds:
                    response_parts.append(f"• \"{cmd}\"")
            
            response_parts.append("\n\n💡 **Tips:**")
            for tip in examples_data['tips']:
                response_parts.append(tip)
            
            return jsonify({
                "success": True,
                "response": "\n".join(response_parts),
                "response_time": 0,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
        
        session_id = session['session_id']
        
        # Get response from the autonomous agent with conversation history
        result = process_logistics_request(user_message, session_id, actor_role=session.get('role', 'owner'))
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "success": False,
            "response": f"Server error: {str(e)}",
            "error_details": traceback.format_exc()
        })

@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "Logistics Agent API",
        "tools_available": TOOLS_AVAILABLE,
        "agent_available": AGENT_AVAILABLE,
        "llm_available": LLM_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/welcome')
def welcome():
    """Get welcome message with quick start guide."""
    return jsonify({
        "message": "👋 Welcome to Logistics Agent!",
        "description": "I can help you manage drivers, vehicles, trips, loads, expenses, and more using natural language.",
        "quick_start": [
            "Try: 'trip 1' to see trip details",
            "Try: 'vehicle 2 summary' for vehicle info",
            "Try: 'create trip with driver 1 and vehicle 2'",
            "Try: 'show trip 1 expenses' for expense breakdown"
        ],
        "features": [
            "✓ Natural language understanding",
            "✓ Context-aware conversations",
            "✓ Automatic ID resolution (names, plates, phones)",
            "✓ Multi-turn task completion",
            "✓ Smart status updates"
        ],
        "need_help": "Type 'help' or 'examples' to see all available commands!"
    })

@app.route('/examples')
def examples():
    """Get example queries for the agent."""
    role = _normalize_role(request.args.get('role') or session.get('role', 'owner'))

    examples_by_role = {
        "customer": {
            "Load Management": [
                "create load customer 1 pickup Mumbai delivery Pune weight 1500kg description electronics",
                "show load 3 details",
                "load 3",
            ],
        },
        "driver": {
            "Trip & Expenses": [
                "trip 1 details",
                "show trip 1 expenses",
                "add expense trip 1 fuel 500 driver 1",
                "driver 1 expenses",
            ],
            "Location Updates": [
                "add location for trip 2 lat 19.0760 lng 72.8777 address Andheri",
            ],
        },
        "owner": {
            "Registration & Setup": [
                "add owner ABC Logistics with email contact@abc.com",
                "register driver Bob Smith email bob@test.com phone 9988776655 owner 1",
                "add vehicle MH12AB3456 with capacity 5000kg for owner 1",
            ],
            "Trip Management": [
                "create trip with driver 1 and vehicle 2",
                "show trip 1 details",
                "show trip 1 expenses",
            ],
            "Load Management": [
                "create load customer 1 pickup Mumbai delivery Pune weight 1500kg description electronics",
                "assign load 2 to trip 1",
                "show load 3 details",
            ],
            "Summaries": [
                "owner 1 summary",
                "vehicle 2 summary",
            ],
        },
    }

    return jsonify({
        "role": role,
        "categories": examples_by_role.get(role, examples_by_role["owner"]),
        "tips": [
            "💡 Your access depends on the selected mode (customer/driver/owner).",
            "💡 Use IDs (trip_id/load_id/driver_id/vehicle_id) when possible for best results.",
            "💡 The agent keeps context within the current session and mode.",
        ],
    })


@app.route('/set_role', methods=['POST'])
def set_role():
    """Set the current UI mode (customer/driver/owner)."""
    try:
        data = request.get_json() or {}
        role = _normalize_role(data.get('role', 'owner'))
        # Ensure session id exists before clearing history
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        _set_session_role(role)
        return jsonify({"success": True, "role": session.get('role', 'owner')})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/clear_history', methods=['POST'])
def clear_history():
    """Clear conversation history for the current session."""
    try:
        if 'session_id' in session:
            session_id = session['session_id']
            if session_id in conversation_histories:
                del conversation_histories[session_id]
            # Create new session
            session['session_id'] = str(uuid.uuid4())
        
        return jsonify({
            "success": True,
            "response": "Conversation history cleared. Starting fresh!"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "response": f"Error clearing history: {str(e)}"
        })

if __name__ == '__main__':
    print("🚚 Starting Logistics Agent Web Interface...")
    print("📱 Access the chat at: http://localhost:5000")
    print("🔧 Health check at: http://localhost:5000/health")
    print("👋 Welcome message: http://localhost:5000/welcome")
    print("📋 Examples API: http://localhost:5000/examples")
    print("\n💡 In chat, type 'help' or 'examples' to see all commands")
    
    if TOOLS_AVAILABLE:
        print("✅ Database tools loaded successfully")
        if AGENT_AVAILABLE:
            print("✅ Intelligent agent available")
        else:
            print("⚠️ Agent not available - using fallback mode")
        if LLM_AVAILABLE:
            print("✅ LLM parsing available")
        else:
            print("⚠️ LLM parsing not available - using pattern matching")
    else:
        print("⚠️ Database tools not available - limited functionality")
    
    app.run(debug=True, host='0.0.0.0', port=5000)