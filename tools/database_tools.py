"""
Database tools for CRUD operations in the logistics system.
Contains all database-related functions as modular tools.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text, Enum
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import enum

# Database setup
DATABASE_URL = "sqlite:///./logistics.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

# Enums
class UserRole(enum.Enum):
    CUSTOMER = "customer"
    DRIVER = "driver"
    OWNER = "owner"

class VehicleStatus(enum.Enum):
    AVAILABLE = "available"
    IN_USE = "in_use"
    MAINTENANCE = "maintenance"
    OUT_OF_SERVICE = "out_of_service"

class LoadStatus(enum.Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class TripStatus(enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ExpenseType(enum.Enum):
    FUEL = "fuel"
    MAINTENANCE = "maintenance"
    TOLL = "toll"
    FOOD = "food"
    ACCOMMODATION = "accommodation"
    OTHER = "other"


class Owner(Base):
    __tablename__ = 'owners'
    
    owner_id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False)
    business_address = Column(Text, nullable=False)
    contact_email = Column(String(255), unique=True, nullable=False)
    gst_number = Column(String(15), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    users = relationship('User', back_populates='owner')
    vehicles = relationship('Vehicle', back_populates='owner')


class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey('owners.owner_id'), nullable=False)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    phone_number = Column(String(20), unique=True, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship('Owner', back_populates='users')
    customer_loads = relationship('Load', foreign_keys='Load.customer_id', back_populates='customer')
    driven_trips = relationship('Trip', back_populates='driver')
    expenses = relationship('Expense', back_populates='user')


class Vehicle(Base):
    __tablename__ = 'vehicles'
    
    vehicle_id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey('owners.owner_id'), nullable=False)
    license_plate = Column(String(20), unique=True, nullable=False)
    capacity_kg = Column(Float, nullable=False)
    status = Column(Enum(VehicleStatus), default=VehicleStatus.AVAILABLE)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    owner = relationship('Owner', back_populates='vehicles')
    trips = relationship('Trip', back_populates='vehicle')


class Load(Base):
    __tablename__ = 'loads'
    
    load_id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    trip_id = Column(Integer, ForeignKey('trips.trip_id'), nullable=True)
    status = Column(Enum(LoadStatus), default=LoadStatus.PENDING)
    pickup_address = Column(Text, nullable=False)
    destination_address = Column(Text, nullable=False)
    weight_kg = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship('User', foreign_keys=[customer_id], back_populates='customer_loads')
    trip = relationship('Trip', back_populates='loads')


class Trip(Base):
    __tablename__ = 'trips'
    
    trip_id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    vehicle_id = Column(Integer, ForeignKey('vehicles.vehicle_id'), nullable=False)
    status = Column(Enum(TripStatus), default=TripStatus.SCHEDULED)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    driver = relationship('User', back_populates='driven_trips')
    vehicle = relationship('Vehicle', back_populates='trips')
    loads = relationship('Load', back_populates='trip')
    expenses = relationship('Expense', back_populates='trip')
    location_updates = relationship('LocationUpdate', back_populates='trip')


class Expense(Base):
    __tablename__ = 'expenses'
    
    expense_id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey('trips.trip_id'), nullable=True)
    driver_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    expense_type = Column(Enum(ExpenseType), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    receipt_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    trip = relationship('Trip', back_populates='expenses')
    user = relationship('User', back_populates='expenses')


class LocationUpdate(Base):
    __tablename__ = 'location_updates'
    
    location_id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey('trips.trip_id'), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    speed_kmh = Column(Float, nullable=True)
    address = Column(Text, nullable=True)
    
    # Relationships
    trip = relationship('Trip', back_populates='location_updates')


# Create tables
Base.metadata.create_all(bind=engine)


def register_owner(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Register a new owner (company) in the database."""
    db = SessionLocal()
    try:
        owner = Owner(
            company_name=parsed_data.get('company_name', 'Unknown Company'),
            business_address=parsed_data.get('business_address', ''),
            contact_email=parsed_data.get('contact_email', ''),
            gst_number=parsed_data.get('gst_number')
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)
        return {"status": "success", "owner_id": owner.owner_id, "message": f"Owner '{owner.company_name}' registered successfully"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Failed to register owner: {str(e)}"}
    finally:
        db.close()


def register_user(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Register a new user (customer, driver, or owner) in the database."""
    db = SessionLocal()
    try:
        # Validate required fields
        required_fields = ['owner_id', 'full_name', 'email', 'password_hash', 'phone_number', 'role']
        for field in required_fields:
            if not parsed_data.get(field):
                return {"status": "error", "message": f"'{field}' is required"}
        
        # Validate owner exists
        owner = db.query(Owner).filter(Owner.owner_id == parsed_data['owner_id']).first()
        if not owner:
            return {"status": "error", "message": f"Owner with ID {parsed_data['owner_id']} not found"}
        
        # Validate role
        try:
            role = UserRole(parsed_data['role'])
        except ValueError:
            return {"status": "error", "message": f"Invalid role: {parsed_data['role']}"}
        
        user = User(
            owner_id=parsed_data['owner_id'],
            full_name=parsed_data['full_name'],
            email=parsed_data['email'],
            password_hash=parsed_data['password_hash'],
            phone_number=parsed_data['phone_number'],
            role=role
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"status": "success", "user_id": user.user_id, "message": f"User '{user.full_name}' registered successfully as {role.value}"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Failed to register user: {str(e)}"}
    finally:
        db.close()


def add_vehicle(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new vehicle to the database."""
    db = SessionLocal()
    try:
        # Validate required fields
        required_fields = ['owner_id', 'license_plate', 'capacity_kg']
        for field in required_fields:
            if parsed_data.get(field) is None:
                return {"status": "error", "message": f"'{field}' is required"}
        
        # Validate owner exists
        owner = db.query(Owner).filter(Owner.owner_id == parsed_data['owner_id']).first()
        if not owner:
            return {"status": "error", "message": f"Owner with ID {parsed_data['owner_id']} not found"}
        
        # Validate status if provided
        status = VehicleStatus.AVAILABLE
        if parsed_data.get('status'):
            try:
                status = VehicleStatus(parsed_data['status'])
            except ValueError:
                return {"status": "error", "message": f"Invalid status: {parsed_data['status']}"}
        
        vehicle = Vehicle(
            owner_id=parsed_data['owner_id'],
            license_plate=parsed_data['license_plate'],
            capacity_kg=float(parsed_data['capacity_kg']),
            status=status
        )
        db.add(vehicle)
        db.commit()
        db.refresh(vehicle)
        return {"status": "success", "vehicle_id": vehicle.vehicle_id, "message": f"Vehicle '{vehicle.license_plate}' added successfully"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Failed to add vehicle: {str(e)}"}
    finally:
        db.close()


def create_load(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new load request."""
    db = SessionLocal()
    try:
        # Validate required fields
        required_fields = ['customer_id', 'pickup_address', 'destination_address']
        for field in required_fields:
            if not parsed_data.get(field):
                return {"status": "error", "message": f"'{field}' is required"}
        
        # Validate customer exists and is a customer
        customer = db.query(User).filter(
            User.user_id == parsed_data['customer_id'],
            User.role == UserRole.CUSTOMER
        ).first()
        if not customer:
            return {"status": "error", "message": f"Customer with ID {parsed_data['customer_id']} not found"}
        
        # Validate status if provided
        status = LoadStatus.PENDING
        if parsed_data.get('status'):
            try:
                status = LoadStatus(parsed_data['status'])
            except ValueError:
                return {"status": "error", "message": f"Invalid status: {parsed_data['status']}"}
        
        load = Load(
            customer_id=parsed_data['customer_id'],
            pickup_address=parsed_data['pickup_address'],
            destination_address=parsed_data['destination_address'],
            weight_kg=parsed_data.get('weight_kg'),
            description=parsed_data.get('description'),
            status=status
        )
        db.add(load)
        db.commit()
        db.refresh(load)
        return {"status": "success", "load_id": load.load_id, "message": f"Load from '{load.pickup_address}' to '{load.destination_address}' created successfully"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Failed to create load: {str(e)}"}
    finally:
        db.close()


def add_trip(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new trip to the database."""
    db = SessionLocal()
    try:
        # Validate required fields
        required_fields = ['driver_id', 'vehicle_id']
        for field in required_fields:
            if not parsed_data.get(field):
                return {"status": "error", "message": f"'{field}' is required"}
        
        # Validate driver exists and is a driver
        driver = db.query(User).filter(
            User.user_id == parsed_data['driver_id'],
            User.role == UserRole.DRIVER
        ).first()
        if not driver:
            return {"status": "error", "message": f"Driver with ID {parsed_data['driver_id']} not found"}
        
        # Validate vehicle exists
        vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == parsed_data['vehicle_id']).first()
        if not vehicle:
            return {"status": "error", "message": f"Vehicle with ID {parsed_data['vehicle_id']} not found"}
        
        # Validate status if provided
        status = TripStatus.SCHEDULED
        if parsed_data.get('status'):
            try:
                status = TripStatus(parsed_data['status'])
            except ValueError:
                return {"status": "error", "message": f"Invalid status: {parsed_data['status']}"}
        
        trip = Trip(
            driver_id=parsed_data['driver_id'],
            vehicle_id=parsed_data['vehicle_id'],
            status=status,
            start_time=parsed_data.get('start_time'),
            end_time=parsed_data.get('end_time')
        )
        db.add(trip)
        db.commit()
        db.refresh(trip)
        return {"status": "success", "trip_id": trip.trip_id, "message": f"Trip created successfully for driver {driver.full_name}"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Failed to add trip: {str(e)}"}
    finally:
        db.close()    


def add_expense(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new expense to the database."""
    db = SessionLocal()
    try:
        # Validate required fields
        required_fields = ['driver_id', 'amount', 'expense_type']
        for field in required_fields:
            if not parsed_data.get(field):
                return {"status": "error", "message": f"'{field}' is required"}
        
        amount = parsed_data['amount']
        if amount <= 0:
            return {"status": "error", "message": "Amount must be greater than 0"}
        
        # Validate driver exists
        driver = db.query(User).filter(User.user_id == parsed_data['driver_id']).first()
        if not driver:
            return {"status": "error", "message": f"User with ID {parsed_data['driver_id']} not found"}
        
        # Validate expense type
        try:
            expense_type = ExpenseType(parsed_data['expense_type'])
        except ValueError:
            return {"status": "error", "message": f"Invalid expense type: {parsed_data['expense_type']}"}
        
        # Validate trip if provided
        trip_id = parsed_data.get('trip_id')
        if trip_id:
            trip = db.query(Trip).filter(Trip.trip_id == trip_id).first()
            if not trip:
                return {"status": "error", "message": f"Trip with ID {trip_id} not found"}
        
        expense = Expense(
            trip_id=trip_id,
            driver_id=parsed_data['driver_id'],
            expense_type=expense_type,
            amount=amount,
            description=parsed_data.get('description'),
            receipt_url=parsed_data.get('receipt_url')
        )
        db.add(expense)
        db.commit()
        db.refresh(expense)
        return {"status": "success", "expense_id": expense.expense_id, "message": f"Expense of ₹{amount} recorded successfully"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Failed to add expense: {str(e)}"}
    finally:
        db.close()


def assign_load_to_trip(load_id: int, trip_id: int) -> Dict[str, Any]:
    """Assign a load to a trip."""
    db = SessionLocal()
    try:
        # Validate load exists
        load = db.query(Load).filter(Load.load_id == load_id).first()
        if not load:
            return {"status": "error", "message": f"Load with ID {load_id} not found"}
        
        # Validate trip exists
        trip = db.query(Trip).filter(Trip.trip_id == trip_id).first()
        if not trip:
            return {"status": "error", "message": f"Trip with ID {trip_id} not found"}
        
        # Assign load to trip
        load.trip_id = trip_id
        load.status = LoadStatus.ASSIGNED
        db.commit()
        
        return {"status": "success", "message": f"Load {load_id} assigned to trip {trip_id} successfully"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Failed to assign load to trip: {str(e)}"}
    finally:
        db.close()


def add_location_update(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a location update for a trip."""
    db = SessionLocal()
    try:
        # Validate required fields
        required_fields = ['trip_id', 'latitude', 'longitude']
        for field in required_fields:
            if parsed_data.get(field) is None:
                return {"status": "error", "message": f"'{field}' is required"}
        
        # Validate trip exists
        trip = db.query(Trip).filter(Trip.trip_id == parsed_data['trip_id']).first()
        if not trip:
            return {"status": "error", "message": f"Trip with ID {parsed_data['trip_id']} not found"}
        
        location_update = LocationUpdate(
            trip_id=parsed_data['trip_id'],
            latitude=parsed_data['latitude'],
            longitude=parsed_data['longitude'],
            speed_kmh=parsed_data.get('speed_kmh'),
            address=parsed_data.get('address')
        )
        db.add(location_update)
        db.commit()
        db.refresh(location_update)
        return {"status": "success", "location_id": location_update.location_id, "message": "Location update added successfully"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Failed to add location update: {str(e)}"}
    finally:
        db.close()


def get_owner_summary(owner_id: int) -> Dict[str, Any]:
    """Get summary information for an owner."""
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.owner_id == owner_id).first()
        if not owner:
            return {"status": "error", "message": f"Owner with ID {owner_id} not found"}
        
        # Get all users under this owner
        users = db.query(User).filter(User.owner_id == owner_id).all()
        user_counts = {}
        for role in UserRole:
            user_counts[role.value] = sum(1 for u in users if u.role == role)
        
        # Get vehicles (not directly owned by owner in new schema, but we can count them)
        total_vehicles = db.query(Vehicle).count()
        available_vehicles = db.query(Vehicle).filter(Vehicle.status == VehicleStatus.AVAILABLE).count()
        
        # Get trips for this owner's drivers
        driver_ids = [u.user_id for u in users if u.role == UserRole.DRIVER]
        trips = db.query(Trip).filter(Trip.driver_id.in_(driver_ids)).all() if driver_ids else []
        
        # Get loads for this owner's customers
        customer_ids = [u.user_id for u in users if u.role == UserRole.CUSTOMER]
        loads = db.query(Load).filter(Load.customer_id.in_(customer_ids)).all() if customer_ids else []
        
        # Get total expenses
        trip_ids = [t.trip_id for t in trips]
        total_expense = 0.0
        if trip_ids:
            expenses = db.query(Expense).filter(Expense.trip_id.in_(trip_ids)).all()
            total_expense = sum(e.amount for e in expenses)
        
        return {
            "status": "success",
            "owner_id": owner_id,
            "company_name": owner.company_name,
            "user_counts": user_counts,
            "total_vehicles": total_vehicles,
            "available_vehicles": available_vehicles,
            "total_trips": len(trips),
            "total_loads": len(loads),
            "total_expense": total_expense
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to get owner summary: {str(e)}"}
    finally:
        db.close()


def get_vehicle_summary(vehicle_id: int) -> Dict[str, Any]:
    """Get summary information for a vehicle."""
    db = SessionLocal()
    try:
        vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).first()
        if not vehicle:
            return {"status": "error", "message": f"Vehicle with ID {vehicle_id} not found"}
        
        trips = db.query(Trip).filter(Trip.vehicle_id == vehicle_id).all()
        trip_ids = [t.trip_id for t in trips]
        
        # Get expenses for this vehicle's trips
        expenses = db.query(Expense).filter(Expense.trip_id.in_(trip_ids)).all() if trip_ids else []
        total_expense = sum(e.amount for e in expenses)
        
        # Group expenses by type
        expense_breakdown = {}
        for expense in expenses:
            expense_type = expense.expense_type.value
            expense_breakdown[expense_type] = expense_breakdown.get(expense_type, 0) + expense.amount
        
        # Get loads handled by this vehicle
        loads = []
        for trip in trips:
            trip_loads = db.query(Load).filter(Load.trip_id == trip.trip_id).all()
            loads.extend(trip_loads)
        
        return {
            "status": "success",
            "vehicle_id": vehicle_id,
            "license_plate": vehicle.license_plate,
            "capacity_kg": vehicle.capacity_kg,
            "status": vehicle.status.value,
            "total_trips": len(trips),
            "total_loads": len(loads),
            "total_expense": total_expense,
            "expense_breakdown": expense_breakdown
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to get vehicle summary: {str(e)}"}
    finally:
        db.close()


def get_trip_details(trip_id: int) -> Dict[str, Any]:
    """Get detailed information for a trip."""
    db = SessionLocal()
    try:
        trip = db.query(Trip).filter(Trip.trip_id == trip_id).first()
        if not trip:
            return {"status": "error", "message": f"Trip with ID {trip_id} not found"}
        
        # Get trip expenses
        expenses = db.query(Expense).filter(Expense.trip_id == trip_id).all()
        total_expense = sum(e.amount for e in expenses)
        
        # Get trip loads
        loads = db.query(Load).filter(Load.trip_id == trip_id).all()
        
        # Get location updates
        location_updates = db.query(LocationUpdate).filter(LocationUpdate.trip_id == trip_id).all()
        
        return {
            "status": "success",
            "trip_id": trip_id,
            "driver_id": trip.driver_id,
            "vehicle_id": trip.vehicle_id,
            "status": trip.status.value,
            "start_time": trip.start_time.isoformat() if trip.start_time else None,
            "end_time": trip.end_time.isoformat() if trip.end_time else None,
            "total_expense": total_expense,
            "expense_count": len(expenses),
            "load_count": len(loads),
            "location_update_count": len(location_updates)
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to get trip details: {str(e)}"}
    finally:
        db.close()


def get_trip_expenses(trip_id: int) -> Dict[str, Any]:
    """Get detailed expense breakdown for a trip: total, count, list, grouped by type."""
    db = SessionLocal()
    try:
        trip = db.query(Trip).filter(Trip.trip_id == trip_id).first()
        if not trip:
            return {"status": "error", "message": f"Trip with ID {trip_id} not found"}
        expenses = db.query(Expense).filter(Expense.trip_id == trip_id).all()
        total = sum(e.amount for e in expenses)
        breakdown: Dict[str, float] = {}
        items = []
        for e in expenses:
            etype = e.expense_type.value
            breakdown[etype] = breakdown.get(etype, 0.0) + e.amount
            items.append({
                "expense_id": e.expense_id,
                "type": etype,
                "amount": e.amount,
                "description": e.description,
                "created_at": e.created_at.isoformat()
            })
        return {
            "status": "success",
            "trip_id": trip_id,
            "total_expense": total,
            "expense_count": len(expenses),
            "expense_breakdown": breakdown,
            "expenses": items
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to get trip expenses: {str(e)}"}
    finally:
        db.close()


def get_user_expenses(user_id: int) -> Dict[str, Any]:
    """Get expense summary for a user (driver)."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return {"status": "error", "message": f"User with ID {user_id} not found"}
        
        expenses = db.query(Expense).filter(Expense.driver_id == user_id).all()
        total_expense = sum(e.amount for e in expenses)
        
        # Group expenses by type
        expense_breakdown = {}
        for expense in expenses:
            expense_type = expense.expense_type.value
            expense_breakdown[expense_type] = expense_breakdown.get(expense_type, 0) + expense.amount
        
        return {
            "status": "success",
            "user_id": user_id,
            "user_name": user.full_name,
            "role": user.role.value,
            "total_expense": total_expense,
            "expense_count": len(expenses),
            "expense_breakdown": expense_breakdown
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to get user expenses: {str(e)}"}
    finally:
        db.close()


def get_load_details(load_id: int) -> Dict[str, Any]:
    """Get detailed information for a load."""
    db = SessionLocal()
    try:
        load = db.query(Load).filter(Load.load_id == load_id).first()
        if not load:
            return {"status": "error", "message": f"Load with ID {load_id} not found"}
        
        # Get customer details
        customer = db.query(User).filter(User.user_id == load.customer_id).first()
        
        # Get trip details if assigned
        trip_details = None
        if load.trip_id:
            trip = db.query(Trip).filter(Trip.trip_id == load.trip_id).first()
            if trip:
                driver = db.query(User).filter(User.user_id == trip.driver_id).first()
                vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == trip.vehicle_id).first()
                trip_details = {
                    "trip_id": trip.trip_id,
                    "driver_name": driver.full_name if driver else None,
                    "vehicle_license": vehicle.license_plate if vehicle else None,
                    "status": trip.status.value
                }
        
        return {
            "status": "success",
            "load_id": load_id,
            "customer_name": customer.full_name if customer else None,
            "pickup_address": load.pickup_address,
            "destination_address": load.destination_address,
            "weight_kg": load.weight_kg,
            "description": load.description,
            "load_status": load.status.value,
            "trip_details": trip_details,
            "created_at": load.created_at.isoformat()
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to get load details: {str(e)}"}
    finally:
        db.close()


def nl_update(text: str) -> Dict[str, Any]:
    """Apply a simple natural-language update to the database in a single instruction.
    Supported examples:
    - "update driver 12 phone 9876543210"
    - "set driver 12 email rahul@example.com"
    - "change vehicle 5 status maintenance"
    - "mark trip 7 completed"
    - "set load 3 status in_transit"
    Returns a dict with status and message.
    """
    import re
    db = SessionLocal()
    try:
        s = text.strip()
        low = s.lower()

        ent_id = re.search(r"\b(driver|user|vehicle|trip|load)\s*(?:id\s*)?(\d+)\b", low)
        ent_kind = None
        ent_pk = None
        if ent_id:
            ent_kind = ent_id.group(1)
            ent_pk = int(ent_id.group(2))

        # Helper: normalize status words
        def norm_status(word: str, kind: str):
            w = word.strip().lower().replace(" ", "_")
            if kind == "vehicle":
                mapping = {"available":"available","in_use":"in_use","inuse":"in_use","maintenance":"maintenance","out_of_service":"out_of_service","outofservice":"out_of_service"}
                return mapping.get(w)
            if kind == "trip":
                mapping = {"scheduled":"scheduled","in_progress":"in_progress","inprogress":"in_progress","completed":"completed","cancelled":"cancelled","canceled":"cancelled"}
                return mapping.get(w)
            if kind == "load":
                mapping = {"pending":"pending","assigned":"assigned","in_transit":"in_transit","intransit":"in_transit","delivered":"delivered","cancelled":"cancelled"}
                return mapping.get(w)
            return None

        if ent_kind in ("driver","user"):
            user = db.query(User).filter(User.user_id == ent_pk).first()
            if not user:
                return {"status":"error","message":f"User/driver with ID {ent_pk} not found"}
            updated = {}
            m = re.search(r"\bphone\b\D*(\+?\d{8,15})", low)
            if m:
                user.phone_number = m.group(1)
                updated["phone_number"] = user.phone_number
            m = re.search(r"([\w.+-]+@[\w.-]+\.[A-Za-z]{2,})", s)
            if m and ("email" in low or "mail" in low):
                user.email = m.group(1)
                updated["email"] = user.email
            m = re.search(r"(?:name\s+to|rename\s+to)\s+([A-Za-z][A-Za-z\s]{1,60})", s)
            if m:
                user.full_name = m.group(1).strip()
                updated["full_name"] = user.full_name
            if not updated:
                return {"status":"error","message":"No supported fields found. Allowed: phone, email, name."}
            db.commit()
            return {"status":"success","message":f"Updated driver/user {user.user_id}", **updated}

        if ent_kind == "vehicle":
            vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == ent_pk).first()
            if not vehicle:
                return {"status":"error","message":"Vehicle not found"}
            updated = {}
            m = re.search(r"status\s+(\w+)", low)
            if m:
                st = norm_status(m.group(1), "vehicle")
                if not st:
                    return {"status":"error","message":"Invalid vehicle status"}
                vehicle.status = VehicleStatus(st)
                updated["status"] = vehicle.status.value
            m = re.search(r"capacity\s*(\d+(?:\.\d+)?)", low)
            if m:
                vehicle.capacity_kg = float(m.group(1))
                updated["capacity_kg"] = vehicle.capacity_kg
            if not updated:
                return {"status":"error","message":"No supported fields found. Allowed: status, capacity."}
            db.commit()
            return {"status":"success","message":f"Updated vehicle {vehicle.vehicle_id}", **updated}

        if ent_kind == "trip":
            trip = db.query(Trip).filter(Trip.trip_id == ent_pk).first()
            if not trip:
                return {"status":"error","message":f"Trip with ID {ent_pk} not found"}
            st = None
            m = re.search(r"status\s+(\w+)", low)
            if m:
                st = norm_status(m.group(1), "trip")
            if not st:
                for cand in ["scheduled","in_progress","inprogress","completed","cancelled","canceled"]:
                    if cand in low:
                        st = norm_status(cand, "trip")
                        break
            if not st:
                return {"status":"error","message":"No valid trip status found"}
            trip.status = TripStatus(st)
            db.commit()
            return {"status":"success","message":f"Updated trip {trip.trip_id}", "status": trip.status.value}

        if ent_kind == "load":
            load = db.query(Load).filter(Load.load_id == ent_pk).first()
            if not load:
                return {"status":"error","message":f"Load with ID {ent_pk} not found"}
            st = None
            m = re.search(r"status\s+(\w+)", low)
            if m:
                st = norm_status(m.group(1), "load")
            if not st:
                for cand in ["pending","assigned","in_transit","intransit","delivered","cancelled"]:
                    if cand in low:
                        st = norm_status(cand, "load")
                        break
            if not st:
                return {"status":"error","message":"No valid load status found"}
            load.status = LoadStatus(st)
            db.commit()
            return {"status":"success","message":f"Updated load {load.load_id}", "status": load.status.value}

        return {"status":"error","message":"Couldn't determine target entity. Use e.g. 'driver 12', 'vehicle 5', 'trip 3', 'load 2'."}
    except Exception as e:
        db.rollback()
        return {"status":"error","message":f"Failed to apply update: {str(e)}"}
    finally:
        db.close()
