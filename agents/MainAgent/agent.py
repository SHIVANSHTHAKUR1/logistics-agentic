# """
# LangGraph graph for the logistics synopsis (SQLite).

# What this file contains:
# - SQLAlchemy models and a simple SQLite DB (logistics.db)
# - Small, focused Python callables that perform DB operations (register owner/driver, add vehicle, add expense, queries)
# - ToolNode wrappers around those callables (small nodes: parse -> db_action -> confirm)
# - A StateGraph that wires the nodes into simple flows for owner registration, driver registration,
#   adding expenses, and owner queries. Transitions are simple and illustrative.

# Notes:
# - The exact LangGraph API surface can vary by version. This file uses a lightweight, explicit style
#   that should be easy to adapt: ToolNode(...) wraps a callable; StateGraph.add_node(...) wires nodes.
# - Replace the `parse_*` functions with LLM/LLM-NLU nodes when you integrate a model in LangGraph.
# - After you verify the nodes work locally, you can connect a WhatsApp webhook to push messages
#   into the appropriate START node (owner/driver/expense flows).

# Run (conceptually):
# - pip install langgraph langchain_core sqlalchemy pydantic
# - python langgraph_sqlite_graph.py  # or import the graph from your LangGraph runner

# """

# from datetime import datetime
# from typing import Optional, Dict, Any
# from langgraph.prebuilt import ToolNode, create_react_agent
# from langgraph.graph import StateGraph, START, END
# from sqlalchemy import (
#     create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text
# )
# from sqlalchemy.orm import declarative_base, sessionmaker, relationship
# import re

# # ----------------------
# # DB setup (SQLite)
# # ----------------------
# DATABASE_URL = "sqlite:///./logistics.db"
# engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
# SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
# Base = declarative_base()


# class Owner(Base):
#     __tablename__ = 'owners'
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String, nullable=False)
#     phone = Column(String, nullable=True)
#     email = Column(String, nullable=True)
#     created_at = Column(DateTime, default=datetime.utcnow)
#     vehicles = relationship('Vehicle', back_populates='owner')


# class Driver(Base):
#     __tablename__ = 'drivers'
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String, nullable=False)
#     phone = Column(String, nullable=True)
#     license_no = Column(String, nullable=True)
#     is_available = Column(Boolean, default=True)
#     created_at = Column(DateTime, default=datetime.utcnow)
#     expenses = relationship('Expense', back_populates='driver')


# class Vehicle(Base):
#     __tablename__ = 'vehicles'
#     id = Column(Integer, primary_key=True, index=True)
#     owner_id = Column(Integer, ForeignKey('owners.id'))
#     reg_no = Column(String, nullable=False)
#     model = Column(String, nullable=True)
#     is_running = Column(Boolean, default=False)
#     created_at = Column(DateTime, default=datetime.utcnow)
#     owner = relationship('Owner', back_populates='vehicles')
#     trips = relationship('Trip', back_populates='vehicle')


# class Trip(Base):
#     __tablename__ = 'trips'
#     id = Column(Integer, primary_key=True, index=True)
#     vehicle_id = Column(Integer, ForeignKey('vehicles.id'))
#     driver_id = Column(Integer, ForeignKey('drivers.id'), nullable=True)
#     origin = Column(String, nullable=True)
#     destination = Column(String, nullable=True)
#     start_time = Column(DateTime, nullable=True)
#     end_time = Column(DateTime, nullable=True)
#     status = Column(String, default='scheduled')
#     created_at = Column(DateTime, default=datetime.utcnow)
#     vehicle = relationship('Vehicle', back_populates='trips')


# class Expense(Base):
#     __tablename__ = 'expenses'
#     id = Column(Integer, primary_key=True, index=True)
#     trip_id = Column(Integer, ForeignKey('trips.id'), nullable=True)
#     driver_id = Column(Integer, ForeignKey('drivers.id'), nullable=True)
#     amount = Column(Float, nullable=False)
#     category = Column(String, nullable=True)
#     note = Column(Text, nullable=True)
#     created_at = Column(DateTime, default=datetime.utcnow)
#     driver = relationship('Driver', back_populates='expenses')


# Base.metadata.create_all(bind=engine)

# # ----------------------
# # Lightweight NL parsers (small nodes)
# # ----------------------

# def parse_owner_nl(text: str) -> Dict[str, Optional[str]]:
#     """Small heuristic parser. Replace with an LLM/intent parser node later."""
#     data = {"name": None, "phone": None, "email": None}
#     m = re.search(r"(?:I am|I'm|This is|Name is)\s+([A-Z][a-zA-Z ]{1,60})", text)
#     if m:
#         data['name'] = m.group(1).strip()
#     else:
#         m2 = re.search(r"([A-Z][a-z]+\s+[A-Z][a-z]+)", text)
#         if m2:
#             data['name'] = m2.group(1)

#     p = re.search(r"(\+?\d{10,13})", text)
#     if p:
#         data['phone'] = p.group(1)

#     e = re.search(r"([\w\.-]+@[\w\.-]+)", text)
#     if e:
#         data['email'] = e.group(1)

#     if not data['name']:
#         data['name'] = 'Unknown Owner'
#     return data


# def parse_driver_nl(text: str) -> Dict[str, Optional[str]]:
#     data = {"name": None, "phone": None, "license_no": None}
#     m = re.search(r"(?:I am|I'm|This is)\s+([A-Z][a-zA-Z ]{1,60})", text)
#     if m:
#         data['name'] = m.group(1).strip()

#     p = re.search(r"(\+?\d{10,13})", text)
#     if p:
#         data['phone'] = p.group(1)

#     lic = re.search(r"([A-Z]{2}\d{1,2}[A-Z]{1,2}\d{1,4})", text)
#     if lic:
#         data['license_no'] = lic.group(1)

#     if not data['name']:
#         data['name'] = 'Unknown Driver'
#     return data


# def parse_expense_nl(text: str) -> Dict[str, Any]:
#     res = {"amount": None, "category": None, "trip_id": None, 'driver_id': None, 'note': text}
#     amt = re.search(r"(Rs\.?\s*|INR\s*)?(\d{2,7}(?:\.\d{1,2})?)", text)
#     if amt:
#         res['amount'] = float(amt.group(2))

#     cat = re.search(r"\b(fuel|toll|food|maintenance|repair|expense|loading|unloading)\b", text, re.IGNORECASE)
#     if cat:
#         res['category'] = cat.group(1).lower()

#     trip = re.search(r"trip\s*(?:id\s*)?(\d+)", text, re.IGNORECASE)
#     if trip:
#         res['trip_id'] = int(trip.group(1))

#     driver = re.search(r"driver\s*(?:id\s*)?(\d+)", text, re.IGNORECASE)
#     if driver:
#         res['driver_id'] = int(driver.group(1))

#     return res

# # ----------------------
# # DB action callables (small nodes)
# # ----------------------

# def db_register_owner(parsed: Dict[str, Optional[str]]) -> Dict[str, Any]:
#     db = SessionLocal()
#     owner = Owner(name=parsed.get('name') or 'Unknown Owner', phone=parsed.get('phone'), email=parsed.get('email'))
#     db.add(owner)
#     db.commit()
#     db.refresh(owner)
#     db.close()
#     return {"status": "ok", "owner_id": owner.id}


# def db_register_driver(parsed: Dict[str, Optional[str]]) -> Dict[str, Any]:
#     db = SessionLocal()
#     driver = Driver(name=parsed.get('name') or 'Unknown Driver', phone=parsed.get('phone'), license_no=parsed.get('license_no'))
#     db.add(driver)
#     db.commit()
#     db.refresh(driver)
#     db.close()
#     return {"status": "ok", "driver_id": driver.id}


# def db_add_vehicle(data: Dict[str, Any]) -> Dict[str, Any]:
#     db = SessionLocal()
#     owner = db.query(Owner).filter(Owner.id == data['owner_id']).first()
#     if not owner:
#         db.close()
#         return {"status": "error", "reason": "owner_not_found"}
#     v = Vehicle(owner_id=data['owner_id'], reg_no=data['reg_no'], model=data.get('model'))
#     db.add(v)
#     db.commit()
#     db.refresh(v)
#     db.close()
#     return {"status": "ok", "vehicle_id": v.id}


# def db_add_expense(parsed: Dict[str, Any]) -> Dict[str, Any]:
#     if parsed.get('amount') is None:
#         return {"status": "error", "reason": "no_amount_found"}
#     db = SessionLocal()
#     e = Expense(trip_id=parsed.get('trip_id'), driver_id=parsed.get('driver_id'), amount=parsed['amount'], category=parsed.get('category'), note=parsed.get('note'))
#     db.add(e)
#     db.commit()
#     db.refresh(e)
#     db.close()
#     return {"status": "ok", "expense_id": e.id}


# def db_owner_summary(owner_id: int) -> Dict[str, Any]:
#     db = SessionLocal()
#     owner = db.query(Owner).filter(Owner.id == owner_id).first()
#     if not owner:
#         db.close()
#         return {"status": "error", "reason": "owner_not_found"}
#     vehicles = db.query(Vehicle).filter(Vehicle.owner_id == owner_id).all()
#     total_vehicles = len(vehicles)
#     running = sum(1 for v in vehicles if v.is_running)
#     vehicle_ids = [v.id for v in vehicles]
#     trips = db.query(Trip).filter(Trip.vehicle_id.in_(vehicle_ids)).all() if vehicle_ids else []
#     trip_ids = [t.id for t in trips]
#     total_expense = 0.0
#     if trip_ids:
#         expenses = db.query(Expense).filter(Expense.trip_id.in_(trip_ids)).all()
#         total_expense = sum(e.amount for e in expenses)
#     db.close()
#     return {"status": "ok", "owner_id": owner_id, "total_vehicles": total_vehicles, "running_vehicles": running, "total_expense_on_trips": total_expense}


# def db_vehicle_expenses(vehicle_id: int) -> Dict[str, Any]:
#     db = SessionLocal()
#     vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
#     if not vehicle:
#         db.close()
#         return {"status": "error", "reason": "vehicle_not_found"}
#     trips = db.query(Trip).filter(Trip.vehicle_id == vehicle_id).all()
#     trip_ids = [t.id for t in trips]
#     expenses = db.query(Expense).filter(Expense.trip_id.in_(trip_ids)).all() if trip_ids else []
#     total = sum(e.amount for e in expenses)
#     db.close()
#     return {"status": "ok", "vehicle_id": vehicle_id, "total_expense": total, "count": len(expenses)}

# # ----------------------
# # Tool nodes (small focused nodes)
# # ----------------------
# # Each ToolNode wraps a small callable. When converting to LangGraph proper, you can
# # replace parse_* nodes with LLM nodes.

# parse_owner_node = ToolNode.from_fn(parse_owner_nl, name='parse_owner_nl')
# register_owner_node = ToolNode.from_fn(db_register_owner, name='db_register_owner')
# confirm_owner_node = ToolNode.from_fn(lambda out: {"message": f"Owner created with id {out.get('owner_id')}"}, name='confirm_owner')

# parse_driver_node = ToolNode.from_fn(parse_driver_nl, name='parse_driver_nl')
# register_driver_node = ToolNode.from_fn(db_register_driver, name='db_register_driver')
# confirm_driver_node = ToolNode.from_fn(lambda out: {"message": f"Driver created with id {out.get('driver_id')}"}, name='confirm_driver')

# parse_expense_node = ToolNode.from_fn(parse_expense_nl, name='parse_expense_nl')
# add_expense_node = ToolNode.from_fn(db_add_expense, name='db_add_expense')
# confirm_expense_node = ToolNode.from_fn(lambda out: {"message": f"Expense recorded id {out.get('expense_id')}"}, name='confirm_expense')

# add_vehicle_node = ToolNode.from_fn(db_add_vehicle, name='db_add_vehicle')
# confirm_vehicle_node = ToolNode.from_fn(lambda out: {"message": f"Vehicle created id {out.get('vehicle_id')}"}, name='confirm_vehicle')

# owner_summary_node = ToolNode.from_fn(db_owner_summary, name='db_owner_summary')
# vehicle_expense_node = ToolNode.from_fn(db_vehicle_expenses, name='db_vehicle_expenses')

# # ----------------------
# # Build the StateGraph
# # ----------------------
# graph = StateGraph(name='logistics_graph')

# # Owner registration flow: START -> parse_owner -> register_owner -> confirm -> END
# graph.add_node(START)
# graph.add_node(parse_owner_node)
# graph.add_node(register_owner_node)
# graph.add_node(confirm_owner_node)
# graph.add_node(END)

# graph.add_edge(START, parse_owner_node)
# # parse -> register: pass parsed dict
# graph.add_edge(parse_owner_node, register_owner_node)
# # register -> confirm
# graph.add_edge(register_owner_node, confirm_owner_node)
# # confirm -> END
# graph.add_edge(confirm_owner_node, END)

# # Driver registration flow (parallel simple flow)
# graph.add_node(parse_driver_node)
# graph.add_node(register_driver_node)
# graph.add_node(confirm_driver_node)
# graph.add_edge(START, parse_driver_node)
# graph.add_edge(parse_driver_node, register_driver_node)
# graph.add_edge(register_driver_node, confirm_driver_node)
# graph.add_edge(confirm_driver_node, END)

# # Expense flow: START -> parse_expense -> add_expense -> confirm -> END
# graph.add_node(parse_expense_node)
# graph.add_node(add_expense_node)
# graph.add_node(confirm_expense_node)
# graph.add_edge(START, parse_expense_node)
# graph.add_edge(parse_expense_node, add_expense_node)
# graph.add_edge(add_expense_node, confirm_expense_node)
# graph.add_edge(confirm_expense_node, END)

# # Vehicle add flow (expects structured input dict with owner_id/reg_no)
# graph.add_node(add_vehicle_node)
# graph.add_node(confirm_vehicle_node)
# graph.add_edge(START, add_vehicle_node)
# graph.add_edge(add_vehicle_node, confirm_vehicle_node)
# graph.add_edge(confirm_vehicle_node, END)

# # Owner query flow: START -> owner_summary_node -> END
# graph.add_node(owner_summary_node)
# graph.add_edge(START, owner_summary_node)
# graph.add_edge(owner_summary_node, END)

# # Vehicle expense query flow: START -> vehicle_expense_node -> END
# graph.add_node(vehicle_expense_node)
# graph.add_edge(START, vehicle_expense_node)
# graph.add_edge(vehicle_expense_node, END)

# # ----------------------
# # Agent (optional): React-agent that can call tools
# # ----------------------
# # Create a small agent that can call the tool nodes above. The agent prompt should
# # be similar to the one you included earlier. Here we create a simple wrapper; when
# # integrating into your LangGraph runtime, connect `graph` to the agent runner.

# agent = create_react_agent(
#     name="logistics_tool_agent",
#     model="your-model-here",  # replace with DEFAULT_MODEL or LangGraph LLM node
#     tools=[
#         parse_owner_node, register_owner_node, confirm_owner_node,
#         parse_driver_node, register_driver_node, confirm_driver_node,
#         parse_expense_node, add_expense_node, confirm_expense_node,
#         add_vehicle_node, confirm_vehicle_node,
#         owner_summary_node, vehicle_expense_node
#     ],
#     prompt=(
#         "You are a LangGraph tool-using agent for a small logistics system.\n"
#         "Use the available small tools (parse_owner_nl, db_register_owner, ...) to perform actions.\n"
#         "Follow Think-Plan-Act-Reflect.\n"
#         "When provided with natural language, select the correct flow: owner-register, driver-register, add-expense, add-vehicle, owner-summary, vehicle-expense.\n"
#         "Do not call external systems outside the provided tools."
#     )
# )

# # ----------------------
# # Export helpers
# # ----------------------

# def get_graph():
#     """Return the graph object so your LangGraph runner can execute it."""
#     return graph


# def get_agent():
#     return agent


# if __name__ == '__main__':
#     print('LangGraph graph created (get_graph()) — import this file into your LangGraph runner.')
