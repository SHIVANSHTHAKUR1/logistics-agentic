#!/usr/bin/env python3
"""
Flask web application for logistics agent chat interface
"""

from flask import Flask, render_template, request, jsonify
from agent import main_agent
import json
import traceback
from datetime import datetime

app = Flask(__name__)

def get_clean_agent_response(user_input: str) -> dict:
    """Get clean agent response with metadata."""
    try:
        start_time = datetime.now()
        
        # Invoke the agent
        response = main_agent.invoke({'user_input': user_input})
        
        end_time = datetime.now()
        response_time = (end_time - start_time).total_seconds()
        
        # Extract final message from the agent
        messages = response.get('messages', [])
        agent_response = "No response generated"
        
        if messages:
            # Get the last AI message (final response)
            for message in reversed(messages):
                if hasattr(message, 'content') and message.content:
                    # Skip tool call messages and get actual response
                    if not (hasattr(message, 'tool_calls') and message.tool_calls):
                        agent_response = message.content
                        break
        
        return {
            "success": True,
            "response": agent_response,
            "response_time": round(response_time, 2),
            "timestamp": end_time.strftime("%H:%M:%S")
        }
        
    except Exception as e:
        return {
            "success": False,
            "response": f"Error: {str(e)}",
            "error_details": traceback.format_exc(),
            "response_time": 0,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

@app.route('/')
def index():
    """Main chat interface."""
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
        
        # Get response from agent
        result = get_clean_agent_response(user_message)
        
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
        "timestamp": datetime.now().isoformat()
    })

@app.route('/examples')
def examples():
    """Get example queries for the agent."""
    examples = [
        {
            "category": "Company Management",
            "examples": [
                "Register company FastTrack Logistics with address Mumbai and email info@fasttrack.com",
                "Show me details for owner ID 1"
            ]
        },
        {
            "category": "Driver Management", 
            "examples": [
                "Add driver Rajesh Kumar with license DL1234567890, phone +91-9876543210",
                "Get driver expenses for driver ID 1"
            ]
        },
        {
            "category": "Vehicle Management",
            "examples": [
                "Add vehicle MH01AB1234 with capacity 5000kg for owner 1",
                "Show vehicle details for vehicle ID 2"
            ]
        },
        {
            "category": "Trip Management",
            "examples": [
                "Create trip with driver 1, vehicle 2 from Mumbai to Pune",
                "Get trip details for trip 3"
            ]
        },
        {
            "category": "Expense Tracking",
            "examples": [
                "Driver 1 spent Rs.500 on fuel for trip 2",
                "Show all expenses for driver ID 1"
            ]
        }
    ]
    
    return jsonify(examples)

if __name__ == '__main__':
    print("🚚 Starting Logistics Agent Web Interface...")
    print("📱 Access the chat at: http://localhost:5000")
    print("🔧 Health check at: http://localhost:5000/health")
    print("📋 Examples at: http://localhost:5000/examples")
    
    app.run(debug=True, host='0.0.0.0', port=5000)