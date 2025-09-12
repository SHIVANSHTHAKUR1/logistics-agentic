"""
Database tools for CRUD operations in the logistics system.
Contains all database-related functions as modular tools.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Database setup
DATABASE_URL = "sqlite:///./logistics.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


class Owner(Base):
    __tablename__ = 'owners'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    vehicles = relationship('Vehicle', back_populates='owner')


class Driver(Base):
    __tablename__ = 'drivers'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    license_no = Column(String, nullable=True)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expenses = relationship('Expense', back_populates='driver')


class Vehicle(Base):
    __tablename__ = 'vehicles'
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey('owners.id'))
    reg_no = Column(String, nullable=False)
    model = Column(String, nullable=True)
    is_running = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner = relationship('Owner', back_populates='vehicles')
    trips = relationship('Trip', back_populates='vehicle')


class Trip(Base):
    __tablename__ = 'trips'
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey('vehicles.id'))
    driver_id = Column(Integer, ForeignKey('drivers.id'), nullable=True)
    origin = Column(String, nullable=True)
    destination = Column(String, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, default='scheduled')
    created_at = Column(DateTime, default=datetime.utcnow)
    vehicle = relationship('Vehicle', back_populates='trips')


class Expense(Base):
    __tablename__ = 'expenses'
    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey('trips.id'), nullable=True)
    driver_id = Column(Integer, ForeignKey('drivers.id'), nullable=True)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    driver = relationship('Driver', back_populates='expenses')


# Create tables
Base.metadata.create_all(bind=engine)


def register_owner(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Register a new owner in the database."""
    db = SessionLocal()
    try:
        owner = Owner(
            name=parsed_data.get('name', 'Unknown Owner'),
            phone=parsed_data.get('phone'),
            email=parsed_data.get('email')
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)
        return {"status": "success", "owner_id": owner.id, "message": f"Owner '{owner.name}' registered successfully"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Failed to register owner: {str(e)}"}
    finally:
        db.close()


def register_driver(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Register a new driver in the database."""
    db = SessionLocal()
    try:
        driver = Driver(
            name=parsed_data.get('name', 'Unknown Driver'),
            phone=parsed_data.get('phone'),
            license_no=parsed_data.get('license_no')
        )
        db.add(driver)
        db.commit()
        db.refresh(driver)
        return {"status": "success", "driver_id": driver.id, "message": f"Driver '{driver.name}' registered successfully"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Failed to register driver: {str(e)}"}
    finally:
        db.close()


def add_vehicle(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new vehicle to the database."""
    db = SessionLocal()
    try:
        owner_id = parsed_data.get('owner_id')
        if not owner_id:
            return {"status": "error", "message": "Owner ID is required to add a vehicle"}
        
        # Check if owner exists
        owner = db.query(Owner).filter(Owner.id == owner_id).first()
        if not owner:
            return {"status": "error", "message": f"Owner with ID {owner_id} not found"}
        
        vehicle = Vehicle(
            owner_id=owner_id,
            reg_no=parsed_data.get('reg_no', 'UNKNOWN'),
            model=parsed_data.get('model')
        )
        db.add(vehicle)
        db.commit()
        db.refresh(vehicle)
        return {"status": "success", "vehicle_id": vehicle.id, "message": f"Vehicle '{vehicle.reg_no}' added successfully"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Failed to add vehicle: {str(e)}"}
    finally:
        db.close()


def add_trip(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new trip to the database."""
    db = SessionLocal()
    try:
        trip = Trip(
            vehicle_id=parsed_data.get('vehicle_id'),
            driver_id=parsed_data.get('driver_id'),
            origin=parsed_data.get('origin'),
            destination=parsed_data.get('destination')
        )
        db.add(trip)
        db.commit()
        db.refresh(trip)
        return {"status": "success", "trip_id": trip.id, "message": f"Trip from '{trip.origin}' to '{trip.destination}' created successfully"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Failed to add trip: {str(e)}"}
    finally:
        db.close()


def add_expense(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new expense to the database."""
    db = SessionLocal()
    try:
        amount = parsed_data.get('amount')
        if amount is None or amount <= 0:
            return {"status": "error", "message": "Valid amount is required for expense"}
        
        expense = Expense(
            trip_id=parsed_data.get('trip_id'),
            driver_id=parsed_data.get('driver_id'),
            amount=amount,
            category=parsed_data.get('category'),
            note=parsed_data.get('note')
        )
        db.add(expense)
        db.commit()
        db.refresh(expense)
        return {"status": "success", "expense_id": expense.id, "message": f"Expense of ₹{amount} recorded successfully"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Failed to add expense: {str(e)}"}
    finally:
        db.close()


def get_owner_summary(owner_id: int) -> Dict[str, Any]:
    """Get summary information for an owner."""
    db = SessionLocal()
    try:
        owner = db.query(Owner).filter(Owner.id == owner_id).first()
        if not owner:
            return {"status": "error", "message": f"Owner with ID {owner_id} not found"}
        
        vehicles = db.query(Vehicle).filter(Vehicle.owner_id == owner_id).all()
        total_vehicles = len(vehicles)
        running_vehicles = sum(1 for v in vehicles if v.is_running)
        
        vehicle_ids = [v.id for v in vehicles]
        trips = db.query(Trip).filter(Trip.vehicle_id.in_(vehicle_ids)).all() if vehicle_ids else []
        trip_ids = [t.id for t in trips]
        
        total_expense = 0.0
        if trip_ids:
            expenses = db.query(Expense).filter(Expense.trip_id.in_(trip_ids)).all()
            total_expense = sum(e.amount for e in expenses)
        
        return {
            "status": "success",
            "owner_id": owner_id,
            "owner_name": owner.name,
            "total_vehicles": total_vehicles,
            "running_vehicles": running_vehicles,
            "total_trips": len(trips),
            "total_expense": total_expense
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to get owner summary: {str(e)}"}
    finally:
        db.close()


def get_vehicle_expenses(vehicle_id: int) -> Dict[str, Any]:
    """Get expense summary for a vehicle."""
    db = SessionLocal()
    try:
        vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
        if not vehicle:
            return {"status": "error", "message": f"Vehicle with ID {vehicle_id} not found"}
        
        trips = db.query(Trip).filter(Trip.vehicle_id == vehicle_id).all()
        trip_ids = [t.id for t in trips]
        expenses = db.query(Expense).filter(Expense.trip_id.in_(trip_ids)).all() if trip_ids else []
        
        total_expense = sum(e.amount for e in expenses)
        expense_breakdown = {}
        for expense in expenses:
            category = expense.category or 'uncategorized'
            expense_breakdown[category] = expense_breakdown.get(category, 0) + expense.amount
        
        return {
            "status": "success",
            "vehicle_id": vehicle_id,
            "vehicle_reg": vehicle.reg_no,
            "total_expense": total_expense,
            "expense_count": len(expenses),
            "expense_breakdown": expense_breakdown
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to get vehicle expenses: {str(e)}"}
    finally:
        db.close()


def get_trip_details(trip_id: int) -> Dict[str, Any]:
    """Get detailed information for a trip."""
    db = SessionLocal()
    try:
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            return {"status": "error", "message": f"Trip with ID {trip_id} not found"}
        
        expenses = db.query(Expense).filter(Expense.trip_id == trip_id).all()
        total_expense = sum(e.amount for e in expenses)
        
        return {
            "status": "success",
            "trip_id": trip_id,
            "origin": trip.origin,
            "destination": trip.destination,
            "vehicle_id": trip.vehicle_id,
            "driver_id": trip.driver_id,
            "status": trip.status,
            "total_expense": total_expense,
            "expense_count": len(expenses)
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to get trip details: {str(e)}"}
    finally:
        db.close()


def get_driver_expenses(driver_id: int) -> Dict[str, Any]:
    """Get expense summary for a driver."""
    db = SessionLocal()
    try:
        driver = db.query(Driver).filter(Driver.id == driver_id).first()
        if not driver:
            return {"status": "error", "message": f"Driver with ID {driver_id} not found"}
        
        expenses = db.query(Expense).filter(Expense.driver_id == driver_id).all()
        total_expense = sum(e.amount for e in expenses)
        
        expense_breakdown = {}
        for expense in expenses:
            category = expense.category or 'uncategorized'
            expense_breakdown[category] = expense_breakdown.get(category, 0) + expense.amount
        
        return {
            "status": "success",
            "driver_id": driver_id,
            "driver_name": driver.name,
            "total_expense": total_expense,
            "expense_count": len(expenses),
            "expense_breakdown": expense_breakdown
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to get driver expenses: {str(e)}"}
    finally:
        db.close()
