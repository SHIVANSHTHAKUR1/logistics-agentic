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
    company_name: str = Field(description="Company/business name")
    business_address: str = Field(description="Business address")
    contact_email: str = Field(description="Contact email address")
    gst_number: Optional[str] = Field(default=None, description="GST number if available")


class UserData(BaseModel):
    """Schema for user registration data."""
    owner_id: int = Field(description="Owner/company ID this user belongs to")
    full_name: str = Field(description="Full name of the user")
    email: str = Field(description="Email address")
    password_hash: str = Field(description="Hashed password")
    phone_number: str = Field(description="Phone number")
    role: str = Field(description="User role: customer, driver, or owner")


class LoadData(BaseModel):
    """Schema for load request data."""
    customer_id: int = Field(description="Customer ID who created the load")
    pickup_address: str = Field(description="Pickup location address")
    destination_address: str = Field(description="Destination address")
    weight_kg: Optional[float] = Field(default=None, description="Weight in kilograms")
    description: Optional[str] = Field(default=None, description="Description of the load")


class LocationData(BaseModel):
    """Schema for location update data."""
    trip_id: int = Field(description="Trip ID this location update belongs to")
    latitude: float = Field(description="GPS latitude coordinate")
    longitude: float = Field(description="GPS longitude coordinate")
    speed_kmh: Optional[float] = Field(default=None, description="Speed in km/h")
    address: Optional[str] = Field(default=None, description="Human readable address")


class DriverData(BaseModel):
    """Schema for driver registration data."""
    name: str = Field(description="Full name of the driver")
    phone: Optional[str] = Field(default=None, description="Phone number")
    email: Optional[str] = Field(default=None, description="Email address")
    license_no: Optional[str] = Field(default="wiehfooweifh", description="Driver's license number")
    owner_id: Optional[int] = Field(default=1, description="Owner/company ID this driver belongs to")


class VehicleData(BaseModel):
    """Schema for vehicle registration data."""
    license_plate: str = Field(description="Vehicle license plate/registration number")
    capacity_kg: float = Field(description="Vehicle capacity in kilograms")
    status: Optional[str] = Field(default="available", description="Vehicle status")


class TripData(BaseModel):
    """Schema for trip data."""
    driver_id: int = Field(description="Driver ID assigned to the trip")
    vehicle_id: int = Field(description="Vehicle ID used for the trip")
    status: Optional[str] = Field(default="scheduled", description="Trip status")


class ExpenseData(BaseModel):
    """Schema for expense data."""
    trip_id: Optional[int] = Field(default=None, description="Trip ID if related to a trip")
    driver_id: int = Field(description="Driver/user ID who submitted the expense")
    expense_type: str = Field(description="Expense type: fuel, toll, food, maintenance, accommodation, other")
    amount: float = Field(description="Expense amount")
    description: Optional[str] = Field(default=None, description="Additional notes about the expense")
    receipt_url: Optional[str] = Field(default=None, description="URL to receipt image")


class LLMParser:
    """LLM-based parser for natural language processing, optimized for Meta Llama 4 Scout model."""
    
    def __init__(self, model=None):
        """Initialize the parser with an LLM model."""
        self.model = model or DEFAULT_MODEL
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        # Llama 4 Scout token limits (conservative estimates)
        self.max_input_tokens = 128000   # 128K context for Llama 4 Scout
        self.max_output_tokens = 4096    # 4K tokens output limit
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough estimation of tokens (1 token ≈ 3.5 characters for Llama models)."""
        return len(text) // 3.5
    
    def _validate_prompt_length(self, prompt: str, operation_name: str) -> bool:
        """Validate that the prompt doesn't exceed Llama's token limits."""
        estimated_tokens = self._estimate_tokens(prompt)
        
        if estimated_tokens > self.max_input_tokens:
            print(f"⚠️ Prompt too long for {operation_name}: {estimated_tokens} tokens (max: {self.max_input_tokens})")
            return False
        
        if estimated_tokens > self.max_input_tokens * 0.8:  # Warning at 80%
            print(f"⚠️ Large prompt for {operation_name}: {estimated_tokens} tokens")
        
        return True
    
    def _invoke_with_retry(self, prompt: str, operation_name: str = "parsing") -> str:
        """Invoke the model with retry logic for Groq/Llama-specific errors."""
        import time
        from langchain_core.messages import HumanMessage
        
        # Validate prompt length before attempting
        if not self._validate_prompt_length(prompt, operation_name):
            raise Exception(f"Prompt too long for {operation_name}")
        
        for attempt in range(self.max_retries):
            try:
                response = self.model.invoke([HumanMessage(content=prompt)])
                return response.content.strip()
            except Exception as e:
                error_msg = str(e).lower()
                
                # Groq/Llama-specific error handling
                if "rate limit" in error_msg or "too many requests" in error_msg:
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                        print(f"⚠️ Rate limit hit during {operation_name}, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                elif "context length" in error_msg or "token limit" in error_msg or "max_tokens" in error_msg:
                    print(f"⚠️ Token limit exceeded during {operation_name}, falling back to simpler prompt...")
                    raise Exception(f"Token limit exceeded in {operation_name}")
                elif "invalid" in error_msg or "bad request" in error_msg:
                    print(f"⚠️ Invalid request during {operation_name}, using fallback...")
                    raise Exception(f"Invalid request in {operation_name}")
                elif "service unavailable" in error_msg or "internal error" in error_msg or "timeout" in error_msg:
                    print(f"⚠️ Groq service error during {operation_name}, retrying...")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                elif "authentication" in error_msg or "api key" in error_msg:
                    print(f"⚠️ Authentication error during {operation_name}")
                    raise Exception(f"API key error in {operation_name}")
                else:
                    print(f"⚠️ Groq API error during {operation_name}: {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                
                # If it's the last attempt, raise the error
                if attempt == self.max_retries - 1:
                    raise Exception(f"All retry attempts failed for {operation_name}: {e}")
        
        return ""
    
    def _clean_llama_json_response(self, content: str) -> str:
        """Clean Llama's JSON response to handle various formatting issues."""
        if not content:
            return "{}"
        
        content = content.strip()
        
        # Remove markdown code blocks (Llama sometimes adds these)
        if content.startswith('```json'):
            content = content[7:]
        elif content.startswith('```'):
            content = content[3:]
        
        if content.endswith('```'):
            content = content[:-3]
        
        # Handle common Llama formatting issues
        content = content.strip()
        
        # Llama sometimes adds explanatory text before/after JSON
        # Look for the first complete JSON object
        start_idx = content.find('{')
        
        if start_idx != -1:
            # Find the matching closing brace for the first opening brace
            brace_count = 0
            end_idx = -1
            
            for i in range(start_idx, len(content)):
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i
                        break
            
            if end_idx != -1:
                content = content[start_idx:end_idx + 1]
        
        # Fix common JSON issues that Llama might produce
        content = content.replace("'", '"')  # Replace single quotes with double quotes
        content = content.replace('True', 'true').replace('False', 'false').replace('None', 'null')
        
        # Llama sometimes adds trailing commas
        import re
        content = re.sub(r',(\s*[}\]])', r'\1', content)
        
        # Handle unquoted keys that Llama might produce
        content = re.sub(r'(\w+):', r'"\1":', content)
        
        return content
    
    def parse_owner(self, text: str) -> Dict[str, Any]:
        """Parse owner registration information from natural language."""
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are a data extraction assistant. Extract owner/company registration information and return ONLY valid JSON.

<|eot_id|><|start_header_id|>user<|end_header_id|>

Extract company information from: "{text}"

Return only a JSON object with these exact fields:
- company_name: Company name (required)
- business_address: Complete address (required) 
- contact_email: Email address (required)
- gst_number: GST number if mentioned, null otherwise

Rules:
1. Return ONLY the JSON object, no explanation
2. Use null for missing optional fields
3. Ensure all strings are properly quoted
4. Create reasonable defaults if information is unclear

Example format:
{{"company_name": "ABC Logistics", "business_address": "123 Main St, Mumbai", "contact_email": "info@abc.com", "gst_number": "12ABCDE3456F7Z8"}}

<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
        
        try:
            content = self._invoke_with_retry(prompt, "owner parsing")
            content = self._clean_llama_json_response(content)
            
            data = OwnerData.model_validate_json(content)
            print(f"🔍 LLM Parsed owner data: {data.model_dump()}")  # Debug output
            return data.model_dump()
        except Exception as e:
            print(f"⚠️ LLM parsing failed, using fallback: {e}")  # Debug output
            # Fallback to basic parsing if LLM fails
            return self._fallback_parse_owner(text)
    
    def parse_user(self, text: str) -> Dict[str, Any]:
        """Parse user registration information from natural language."""
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are a data extraction assistant. Extract user registration information and return ONLY valid JSON.

<|eot_id|><|start_header_id|>user<|end_header_id|>

Extract user information from: "{text}"

Return only a JSON object with these exact fields:
- owner_id: Company ID (use 1 if not specified)
- full_name: Complete name (required)
- email: Email address (required)
- password_hash: Generate as "temp_hash_[name]" (required)
- phone_number: Phone number (required)
- role: Must be "customer", "driver", or "owner" (required)

Rules:
1. Return ONLY the JSON object, no explanation
2. Clean name for password_hash (lowercase, replace spaces with underscores)
3. Default role to "customer" if unclear
4. Create professional email if not provided

Example:
{{"owner_id": 1, "full_name": "John Doe", "email": "john.doe@company.com", "password_hash": "temp_hash_john_doe", "phone_number": "+919876543210", "role": "driver"}}

<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
        
        try:
            content = self._invoke_with_retry(prompt, "user parsing")
            content = self._clean_llama_json_response(content)
            
            data = UserData.model_validate_json(content)
            print(f"🔍 LLM Parsed user data: {data.model_dump()}")
            return data.model_dump()
        except Exception as e:
            print(f"⚠️ LLM parsing failed, using fallback: {e}")
            return self._fallback_parse_user(text)
    
    def parse_load(self, text: str) -> Dict[str, Any]:
        """Parse load request information from natural language."""
        prompt = f"""You are a data extraction assistant. Extract load/shipment request information from the user input.

Input text: "{text}"

TASK: Extract the following information and return ONLY a valid JSON object:

REQUIRED FIELDS:
- customer_id: Customer ID who created the load (use 1 if not specified)
- pickup_address: Complete pickup location address
- destination_address: Complete destination address

OPTIONAL FIELDS:
- weight_kg: Weight in kilograms (null if not mentioned)
- description: Description of the load/cargo (null if not provided)

INSTRUCTIONS:
1. Return ONLY valid JSON, no markdown formatting
2. Addresses should be as complete as possible
3. Weight should be numeric (convert from other units if needed)
4. Look for keywords like "from", "to", "pickup", "delivery", "destination"
5. If addresses are incomplete, make reasonable assumptions

EXAMPLE OUTPUT:
{{"customer_id": 1, "pickup_address": "Warehouse A, Mumbai Port", "destination_address": "Factory B, Pune Industrial Area", "weight_kg": 500.0, "description": "Electronic components"}}
"""
        
        try:
            content = self._invoke_with_retry(prompt, "load parsing")
            content = self._clean_llama_json_response(content)
            
            data = LoadData.model_validate_json(content)
            print(f"🔍 LLM Parsed load data: {data.model_dump()}")
            return data.model_dump()
        except Exception as e:
            print(f"⚠️ LLM parsing failed, using fallback: {e}")
            return self._fallback_parse_load(text)
    
    def parse_location(self, text: str) -> Dict[str, Any]:
        """Parse location update information from natural language."""
        prompt = f"""
        Extract location update information from the following text:
        "{text}"
        
        Return a JSON object with the following structure:
        - trip_id: Trip ID this location belongs to (required)
        - latitude: GPS latitude coordinate (required)
        - longitude: GPS longitude coordinate (required)
        - speed_kmh: Speed in km/h if mentioned
        - address: Human readable address if mentioned
        
        If any information is not clear, make reasonable assumptions.
        """
        
        try:
            content = self._invoke_with_retry(prompt, "location parsing")
            content = self._clean_llama_json_response(content)
            
            data = LocationData.model_validate_json(content)
            print(f"🔍 LLM Parsed location data: {data.model_dump()}")
            return data.model_dump()
        except Exception as e:
            print(f"⚠️ LLM parsing failed, using fallback: {e}")
            return self._fallback_parse_location(text)
    
    def parse_driver(self, text: str) -> Dict[str, Any]:
        """Parse driver registration information from natural language."""
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are a data extraction assistant. Extract driver registration information and return ONLY valid JSON.

<|eot_id|><|start_header_id|>user<|end_header_id|>

Extract driver information from: "{text}"

Return only a JSON object with these exact fields:
- name: Complete driver name (required)
- phone: Phone number with country code if available (null if not found)
- email: Email address (null if not found)
- license_no: Driver's license number (null if not found)
- owner_id: Owner/company ID number that this driver belongs to (extract from text, or default to 1)

Email patterns to look for:
- Standard email format: username@domain.com
- Any string containing @ symbol with text before and after

License patterns to look for:
- DL followed by numbers (DL1234567890)
- State codes + numbers (MH01234567890)
- Any alphanumeric sequence 8-15 characters

Owner ID patterns to look for:
- "owner id X", "owner X", "company X", "for owner X"
- Default to 1 if not specified

Rules:
1. Return ONLY the JSON object, no explanation
2. Use null for missing optional fields
3. Ensure all strings are properly quoted
4. Extract numeric owner_id from text patterns

Example:
{{"name": "John Smith", "phone": "+919876543210", "email": "john@example.com", "license_no": "DL1234567890", "owner_id": 1}}

<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
        
        try:
            content = self._invoke_with_retry(prompt, "driver parsing")
            content = self._clean_llama_json_response(content)
            
            data = DriverData.model_validate_json(content)
            print(f"🔍 LLM Parsed driver data: {data.model_dump()}")  # Debug output
            return data.model_dump()
        except Exception as e:
            print(f"⚠️ LLM parsing failed, using fallback: {e}")  # Debug output
            return self._fallback_parse_driver(text)
    
    def parse_vehicle(self, text: str) -> Dict[str, Any]:
        """Parse vehicle registration information from natural language."""
        prompt = f"""You are a data extraction assistant. Extract vehicle registration information from the user input.

Input text: "{text}"

TASK: Extract the following information and return ONLY a valid JSON object:

REQUIRED FIELDS:
- license_plate: Vehicle registration/license plate number
- capacity_kg: Vehicle cargo capacity in kilograms

OPTIONAL FIELDS:
- status: Vehicle status ("available", "in_use", "maintenance", "out_of_service") - default "available"

INSTRUCTIONS:
1. Return ONLY valid JSON, no markdown formatting
2. License plate should be uppercase, remove spaces/special chars
3. Convert capacity to kg (from tons, pounds, etc. if needed)
4. Status must be one of the specified values
5. Look for vehicle registration patterns (state codes + numbers)

CAPACITY CONVERSION:
- 1 ton = 1000 kg
- 1 pound = 0.453592 kg

EXAMPLE OUTPUT:
{{"license_plate": "MH01AB1234", "capacity_kg": 5000.0, "status": "available"}}
"""
        
        try:
            content = self._invoke_with_retry(prompt, "vehicle parsing")
            content = self._clean_llama_json_response(content)
            
            data = VehicleData.model_validate_json(content)
            return data.model_dump()
        except Exception as e:
            return self._fallback_parse_vehicle(text)
    
    def parse_trip(self, text: str) -> Dict[str, Any]:
        """Parse trip information from natural language."""
        prompt = f"""
        Extract trip information from the following text:
        "{text}"
        
        Return a JSON object with the following structure:
        - driver_id: Driver ID assigned to the trip (required)
        - vehicle_id: Vehicle ID used for the trip (required)
        - status: Trip status (scheduled, in_progress, completed, cancelled)
        
        If any information is not clear, make reasonable assumptions.
        """
        
        try:
            content = self._invoke_with_retry(prompt, "trip parsing")
            content = self._clean_llama_json_response(content)
            
            data = TripData.model_validate_json(content)
            return data.model_dump()
        except Exception as e:
            return self._fallback_parse_trip(text)
    
    def parse_expense(self, text: str) -> Dict[str, Any]:
        """Parse expense information from natural language."""
        prompt = f"""You are a data extraction assistant. Extract expense information from the user input.

Input text: "{text}"

TASK: Extract the following information and return ONLY a valid JSON object:

REQUIRED FIELDS:
- driver_id: Driver/user ID who submitted the expense
- expense_type: Type of expense (must be: "fuel", "maintenance", "toll", "food", "accommodation", "other")
- amount: Expense amount as a number (no currency symbols)

OPTIONAL FIELDS:
- trip_id: Trip ID if expense is related to a specific trip (null if not specified)
- description: Additional details about the expense (null if not provided)
- receipt_url: URL to receipt image if mentioned (null if not provided)

INSTRUCTIONS:
1. Return ONLY valid JSON, no markdown formatting
2. Remove currency symbols (₹, Rs, $) from amount
3. Expense type must match exactly one of the allowed values
4. If type is unclear, use "other"
5. Amount should be numeric (convert from text if needed)

EXPENSE TYPE MAPPING:
- fuel, petrol, diesel, gas → "fuel"
- repair, service, maintenance → "maintenance"  
- toll, tax, highway → "toll"
- food, meal, snacks → "food"
- hotel, lodge, accommodation → "accommodation"
- anything else → "other"

EXAMPLE OUTPUT:
{{"driver_id": 1, "expense_type": "fuel", "amount": 1500.0, "trip_id": 5, "description": "Diesel for Mumbai-Pune trip", "receipt_url": null}}
"""
        
        try:
            content = self._invoke_with_retry(prompt, "expense parsing")
            content = self._clean_llama_json_response(content)
            
            data = ExpenseData.model_validate_json(content)
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
        
        print(f"🔍 Fallback parsed owner data: {data}")  # Debug output
        return data
    
    def _fallback_parse_driver(self, text: str) -> Dict[str, Any]:
        """Fallback parsing for driver data using regex."""
        import re
        data = {"name": "Unknown Driver", "phone": None, "email": None, "license_no": None, "owner_id": 1}
        
        # Extract name - more flexible patterns
        name_patterns = [
            r"(?:add\s+driver\s+|driver\s+)([A-Z][a-zA-Z\s]{1,60}?)(?:\s*,|\s+phone|\s+email|\s+license|\s+owner)",
            r"(?:I am|I'm|This is|Name is|My name is)\s+([A-Z][a-zA-Z ]{1,60})",
            r"([A-Z][a-z]+\s+[A-Z][a-z]+)",  # First Last format
        ]
        
        for pattern in name_patterns:
            name_match = re.search(pattern, text, re.IGNORECASE)
            if name_match:
                data['name'] = name_match.group(1).strip()
                break
        
        # Extract email - flexible patterns
        email_patterns = [
            r"email\s*:?\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",  # "email: user@domain.com"
            r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",  # Standard email pattern
        ]
        
        for pattern in email_patterns:
            email_match = re.search(pattern, text, re.IGNORECASE)
            if email_match:
                data['email'] = email_match.group(1)
                break
        
        # Extract phone - more flexible patterns
        phone_patterns = [
            r"phone\s*:?\s*(\+?\d{10,13})",  # "phone: 1234567890"
            r"contact\s*:?\s*(\+?\d{10,13})",  # "contact: 1234567890"
            r"(\+?\d{10,13})",  # Standard phone
        ]
        
        for pattern in phone_patterns:
            phone_match = re.search(pattern, text, re.IGNORECASE)
            if phone_match:
                data['phone'] = phone_match.group(1)
                break
        
        # Extract license - more flexible patterns
        license_patterns = [
            r"license\s*:?\s*([A-Z0-9]{6,15})",  # "license: BR123456789"
            r"license\s+(?:no|number)\s*:?\s*([A-Z0-9]{6,15})",  # "license no: BR123456789"
            r"([A-Z]{2,3}\d{6,12})",  # License format like BR123456789
        ]
        
        for pattern in license_patterns:
            license_match = re.search(pattern, text, re.IGNORECASE)
            if license_match:
                data['license_no'] = license_match.group(1)
                break
        
        # Extract owner_id - more flexible patterns
        owner_patterns = [
            r"owner\s+id\s*:?\s*(\d+)",  # "owner id 1"
            r"owner\s*:?\s*(\d+)",  # "owner: 1" 
            r"company\s+id\s*:?\s*(\d+)",  # "company id 1"
            r"company\s*:?\s*(\d+)",  # "company: 1"
        ]
        
        for pattern in owner_patterns:
            owner_match = re.search(pattern, text, re.IGNORECASE)
            if owner_match:
                data['owner_id'] = int(owner_match.group(1))
                break
        
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
        import re
        data = {"driver_id": None, "vehicle_id": None, "status": "scheduled"}
        
        # Extract driver ID
        driver_match = re.search(r"driver\s*(?:id\s*)?(\d+)", text, re.IGNORECASE)
        if driver_match:
            data['driver_id'] = int(driver_match.group(1))
        
        # Extract vehicle ID  
        vehicle_match = re.search(r"vehicle\s*(?:id\s*)?(\d+)", text, re.IGNORECASE)
        if vehicle_match:
            data['vehicle_id'] = int(vehicle_match.group(1))
        
        return data
    
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
    
    def _fallback_parse_user(self, text: str) -> Dict[str, Any]:
        """Fallback parsing for user data using regex."""
        import re
        data = {
            "owner_id": 1,
            "full_name": "Unknown User",
            "email": "user@company.com",
            "password_hash": "temp_hash_unknown",
            "phone_number": "0000000000",
            "role": "customer"
        }
        
        # Extract name
        name_match = re.search(r"(?:I am|name is|name:)\s+([A-Za-z\s]+)", text, re.IGNORECASE)
        if name_match:
            name = name_match.group(1).strip()
            data['full_name'] = name
            data['password_hash'] = f"temp_hash_{name.replace(' ', '_').lower()}"
        
        # Extract phone
        phone_match = re.search(r"(?:phone|mobile|contact).*?(\+?[0-9\-\s]{10,15})", text, re.IGNORECASE)
        if phone_match:
            phone = re.sub(r'[^\d+]', '', phone_match.group(1))
            data['phone_number'] = phone
        
        # Extract email
        email_match = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", text)
        if email_match:
            data['email'] = email_match.group(1)
        
        # Extract role
        role_match = re.search(r"\b(customer|driver|owner)\b", text, re.IGNORECASE)
        if role_match:
            data['role'] = role_match.group(1).lower()
        
        return data
    
    def _fallback_parse_load(self, text: str) -> Dict[str, Any]:
        """Fallback parsing for load data using regex."""
        import re
        data = {
            "customer_id": 1,
            "pickup_address": "Pickup address not specified",
            "destination_address": "Destination not specified",
            "weight_kg": None,
            "description": text
        }
        
        # Extract pickup
        pickup_match = re.search(r"(?:from|pickup).*?([A-Za-z\s,]+?)(?:to|destination)", text, re.IGNORECASE)
        if pickup_match:
            data['pickup_address'] = pickup_match.group(1).strip()
        
        # Extract destination
        dest_match = re.search(r"(?:to|destination).*?([A-Za-z\s,]+)", text, re.IGNORECASE)
        if dest_match:
            data['destination_address'] = dest_match.group(1).strip()
        
        # Extract weight
        weight_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|kilograms?|tonnes?)", text, re.IGNORECASE)
        if weight_match:
            data['weight_kg'] = float(weight_match.group(1))
        
        return data
    
    def _fallback_parse_location(self, text: str) -> Dict[str, Any]:
        """Fallback parsing for location data using regex."""
        import re
        data = {
            "trip_id": 1,
            "latitude": 0.0,
            "longitude": 0.0,
            "speed_kmh": None,
            "address": None
        }
        
        # Extract trip ID
        trip_match = re.search(r"trip\s*(?:id\s*)?(\d+)", text, re.IGNORECASE)
        if trip_match:
            data['trip_id'] = int(trip_match.group(1))
        
        # Extract coordinates
        coord_match = re.search(r"lat(?:itude)?[:\s]*([+-]?\d+(?:\.\d+)?)[,\s]+lon(?:gitude)?[:\s]*([+-]?\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if coord_match:
            data['latitude'] = float(coord_match.group(1))
            data['longitude'] = float(coord_match.group(2))
        
        # Extract speed
        speed_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:km/h|kmph|kph)", text, re.IGNORECASE)
        if speed_match:
            data['speed_kmh'] = float(speed_match.group(1))
        
        return data


# Global parser instance
_parser_instance = None

def get_parser() -> LLMParser:
    """Get the global parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = LLMParser()
    return _parser_instance
