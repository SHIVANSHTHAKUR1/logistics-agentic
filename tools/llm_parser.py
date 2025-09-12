"""
LLM-based parser for natural language processing in logistics system.
Uses a single LLM instance for consistent parsing across different data types.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from llms import DEFAULT_MODEL


class OwnerData(BaseModel):
    """Schema for owner registration data."""
    name: str = Field(description="Full name of the owner")
    phone: Optional[str] = Field(default=None, description="Phone number")
    email: Optional[str] = Field(default=None, description="Email address")


class DriverData(BaseModel):
    """Schema for driver registration data."""
    name: str = Field(description="Full name of the driver")
    phone: Optional[str] = Field(default=None, description="Phone number")
    license_no: Optional[str] = Field(default="wiehfooweifh", description="Driver's license number")


class VehicleData(BaseModel):
    """Schema for vehicle registration data."""
    reg_no: str = Field(description="Vehicle registration number")
    model: Optional[str] = Field(default=None, description="Vehicle model")
    owner_id: Optional[int] = Field(default=None, description="Owner ID if known")


class TripData(BaseModel):
    """Schema for trip data."""
    origin: Optional[str] = Field(default=None, description="Trip origin location")
    destination: Optional[str] = Field(default=None, description="Trip destination location")
    vehicle_id: Optional[int] = Field(default=None, description="Vehicle ID")
    driver_id: Optional[int] = Field(default=None, description="Driver ID")


class ExpenseData(BaseModel):
    """Schema for expense data."""
    amount: float = Field(description="Expense amount")
    category: Optional[str] = Field(default=None, description="Expense category (fuel, toll, food, maintenance, etc.)")
    trip_id: Optional[int] = Field(default=None, description="Trip ID if related to a trip")
    driver_id: Optional[int] = Field(default=None, description="Driver ID if related to a driver")
    note: Optional[str] = Field(default=None, description="Additional notes about the expense")


class LLMParser:
    """LLM-based parser for natural language processing."""
    
    def __init__(self, model=None):
        """Initialize the parser with an LLM model."""
        self.model = model or DEFAULT_MODEL
    
    def parse_owner(self, text: str) -> Dict[str, Any]:
        """Parse owner registration information from natural language."""
        prompt = f"""
        Extract owner registration information from the following text:
        "{text}"
        
        Return a JSON object with the following structure:
        - name: Full name of the owner (required)
        - phone: Phone number if mentioned
        - email: Email address if mentioned
        
        If any information is not clear or missing, use null for optional fields.
        Always provide a name, even if you have to make a reasonable assumption.
        """
        
        try:
            response = self.model.invoke([HumanMessage(content=prompt)])
            # Parse the response and validate against schema
            data = OwnerData.model_validate_json(response.content)
            return data.model_dump()
        except Exception as e:
            # Fallback to basic parsing if LLM fails
            return self._fallback_parse_owner(text)
    
    def parse_driver(self, text: str) -> Dict[str, Any]:
        """Parse driver registration information from natural language."""
        prompt = f"""
        Extract driver registration information from the following text:
        "{text}"
        
        Return a JSON object with the following structure:
        - name: Full name of the driver (required)
        - phone: Phone number if mentioned
        - license_no: Driver's license number if mentioned
        
        If any information is not clear or missing, use null for optional fields.
        Always provide a name, even if you have to make a reasonable assumption.
        """
        
        try:
            response = self.model.invoke([HumanMessage(content=prompt)])
            data = DriverData.model_validate_json(response.content)
            return data.model_dump()
        except Exception as e:
            return self._fallback_parse_driver(text)
    
    def parse_vehicle(self, text: str) -> Dict[str, Any]:
        """Parse vehicle registration information from natural language."""
        prompt = f"""
        Extract vehicle registration information from the following text:
        "{text}"
        
        Return a JSON object with the following structure:
        - reg_no: Vehicle registration number (required)
        - model: Vehicle model if mentioned
        - owner_id: Owner ID if mentioned
        
        If any information is not clear or missing, use null for optional fields.
        Always provide a reg_no, even if you have to make a reasonable assumption.
        """
        
        try:
            response = self.model.invoke([HumanMessage(content=prompt)])
            data = VehicleData.model_validate_json(response.content)
            return data.model_dump()
        except Exception as e:
            return self._fallback_parse_vehicle(text)
    
    def parse_trip(self, text: str) -> Dict[str, Any]:
        """Parse trip information from natural language."""
        prompt = f"""
        Extract trip information from the following text:
        "{text}"
        
        Return a JSON object with the following structure:
        - origin: Trip origin location if mentioned
        - destination: Trip destination location if mentioned
        - vehicle_id: Vehicle ID if mentioned
        - driver_id: Driver ID if mentioned
        
        If any information is not clear or missing, use null for optional fields.
        """
        
        try:
            response = self.model.invoke([HumanMessage(content=prompt)])
            data = TripData.model_validate_json(response.content)
            return data.model_dump()
        except Exception as e:
            return self._fallback_parse_trip(text)
    
    def parse_expense(self, text: str) -> Dict[str, Any]:
        """Parse expense information from natural language."""
        prompt = f"""
        Extract expense information from the following text:
        "{text}"
        
        Return a JSON object with the following structure:
        - amount: Expense amount (required, as a number)
        - category: Expense category (fuel, toll, food, maintenance, repair, loading, unloading, etc.)
        - trip_id: Trip ID if related to a trip
        - driver_id: Driver ID if related to a driver
        - note: Additional notes about the expense
        
        If any information is not clear or missing, use null for optional fields.
        Always provide an amount, even if you have to make a reasonable assumption.
        """
        
        try:
            response = self.model.invoke([HumanMessage(content=prompt)])
            data = ExpenseData.model_validate_json(response.content)
            return data.model_dump()
        except Exception as e:
            return self._fallback_parse_expense(text)
    
    def _fallback_parse_owner(self, text: str) -> Dict[str, Any]:
        """Fallback parsing for owner data using regex."""
        import re
        data = {"name": "Unknown Owner", "phone": None, "email": None}
        
        # Extract name
        name_match = re.search(r"(?:I am|I'm|This is|Name is)\s+([A-Z][a-zA-Z ]{1,60})", text)
        if name_match:
            data['name'] = name_match.group(1).strip()
        else:
            name_match2 = re.search(r"([A-Z][a-z]+\s+[A-Z][a-z]+)", text)
            if name_match2:
                data['name'] = name_match2.group(1)
        
        # Extract phone
        phone_match = re.search(r"(\+?\d{10,13})", text)
        if phone_match:
            data['phone'] = phone_match.group(1)
        
        # Extract email
        email_match = re.search(r"([\w\.-]+@[\w\.-]+)", text)
        if email_match:
            data['email'] = email_match.group(1)
        
        return data
    
    def _fallback_parse_driver(self, text: str) -> Dict[str, Any]:
        """Fallback parsing for driver data using regex."""
        import re
        data = {"name": "Unknown Driver", "phone": None, "license_no": None}
        
        name_match = re.search(r"(?:I am|I'm|This is)\s+([A-Z][a-zA-Z ]{1,60})", text)
        if name_match:
            data['name'] = name_match.group(1).strip()
        
        phone_match = re.search(r"(\+?\d{10,13})", text)
        if phone_match:
            data['phone'] = phone_match.group(1)
        
        license_match = re.search(r"([A-Z]{2}\d{1,2}[A-Z]{1,2}\d{1,4})", text)
        if license_match:
            data['license_no'] = license_match.group(1)
        
        return data
    
    def _fallback_parse_vehicle(self, text: str) -> Dict[str, Any]:
        """Fallback parsing for vehicle data using regex."""
        import re
        data = {"reg_no": "UNKNOWN", "model": None, "owner_id": None}
        
        reg_match = re.search(r"([A-Z]{2}\d{2}[A-Z]{1,2}\d{4})", text)
        if reg_match:
            data['reg_no'] = reg_match.group(1)
        
        return data
    
    def _fallback_parse_trip(self, text: str) -> Dict[str, Any]:
        """Fallback parsing for trip data using regex."""
        return {
            "origin": None,
            "destination": None,
            "vehicle_id": None,
            "driver_id": None
        }
    
    def _fallback_parse_expense(self, text: str) -> Dict[str, Any]:
        """Fallback parsing for expense data using regex."""
        import re
        data = {"amount": 0.0, "category": None, "trip_id": None, "driver_id": None, "note": text}
        
        amount_match = re.search(r"(Rs\.?\s*|INR\s*)?(\d{2,7}(?:\.\d{1,2})?)", text)
        if amount_match:
            data['amount'] = float(amount_match.group(2))
        
        category_match = re.search(r"\b(fuel|toll|food|maintenance|repair|expense|loading|unloading)\b", text, re.IGNORECASE)
        if category_match:
            data['category'] = category_match.group(1).lower()
        
        trip_match = re.search(r"trip\s*(?:id\s*)?(\d+)", text, re.IGNORECASE)
        if trip_match:
            data['trip_id'] = int(trip_match.group(1))
        
        driver_match = re.search(r"driver\s*(?:id\s*)?(\d+)", text, re.IGNORECASE)
        if driver_match:
            data['driver_id'] = int(driver_match.group(1))
        
        return data


# Global parser instance
_parser_instance = None

def get_parser() -> LLMParser:
    """Get the global parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = LLMParser()
    return _parser_instance
