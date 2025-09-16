#!/usr/bin/env python3
"""
Flask web application for logistics chat interface
Integrates with the full LangGraph agent for intelligent tool selection
"""

from flask import Flask, render_template, request, jsonify
import json
import traceback
from datetime import datetime

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

def process_logistics_request(user_input: str) -> dict:
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
                # Invoke the LangGraph agent with fresh state for autonomous operation
                result = main_agent.invoke({
                    "messages": [],
                    "user_input": user_input,
                    "next_action": "agent"
                })
                
                # Extract the final response from messages
                result_messages = result.get("messages", [])
                if result_messages:
                    # Get the last AI message
                    for msg in reversed(result_messages):
                        if hasattr(msg, 'content') and msg.content.strip():
                            response_text = msg.content
                            break
                    else:
                        response_text = "The agent processed your request but didn't provide a response."
                else:
                    response_text = "No response received from the agent."
                
                success = True
                
            except Exception as e:
                response_text = f"Agent error: {str(e)}"
                success = False
                print(f"Agent execution error: {e}")
                traceback.print_exc()
        
        # Fallback to pattern matching if agent is not available
        else:
            response_text = """🚚 Agent not available. I can help you with:

🏢 **Company Management**: "Register company ABC Logistics with address Mumbai and email info@abc.com"
👨‍💼 **Driver Management**: "Add driver John Doe with license DL123456789, phone +91-9876543210"  
🚛 **Vehicle Management**: "Add vehicle MH01AB1234 with capacity 5000kg for owner 1"
🛣️ **Trip Management**: "Create trip with driver 1 and vehicle 2"
📦 **Load Management**: "Create load for customer 1 from Mumbai to Pune with 1000kg electronics"
🔗 **Load Assignment**: "Assign load 1 to trip 2"
📍 **Location Tracking**: "Update location for trip 1 lat 19.0760 lng 72.8777 at Mumbai"
💰 **Expense Tracking**: "Driver 1 spent Rs.500 on fuel for trip 2"
📊 **Reports**: "Show owner ID 1 details", "Get trip 3 details", "Give me details of load 5", or "Show vehicle ID 2 details"

Please try one of these operations or check the agent configuration!"""
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
        
        if not user_message:
            return jsonify({
                "success": False,
                "response": "Please enter a message."
            })
        
        # Get response from the autonomous agent
        result = process_logistics_request(user_message)
        
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

@app.route('/examples')
def examples():
    """Get example queries for the agent."""
    return jsonify({
        "examples": [
            "Register company ABC Logistics with address Mumbai and email info@abc.com",
            "Add driver John Doe with license DL123456789, phone +91-9876543210",
            "Add vehicle MH01AB1234 with capacity 5000kg for owner 1",
            "Create trip with driver 1 and vehicle 2",
            "Create load for customer 1 from Mumbai to Pune with 1000kg electronics",
            "Assign load 1 to trip 2",
            "Driver 1 spent Rs.500 on fuel for trip 2",
            "Show owner ID 1 details",
            "Get trip 3 details",
            "Give me details of load 5",
            "Show vehicle ID 2 details",
            "Show driver ID 1 expenses"
        ]
    })

if __name__ == '__main__':
    print("🚚 Starting Logistics Agent Web Interface...")
    print("📱 Access the chat at: http://localhost:5000")
    print("🔧 Health check at: http://localhost:5000/health")
    print("📋 Examples at: http://localhost:5000/examples")
    
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