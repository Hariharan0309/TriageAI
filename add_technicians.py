import os
from google.cloud import firestore

# --- Configuration ---
PROJECT_ID = "valued-mediator-461216-k7"
DATABASE_ID = "triageai"
COLLECTION_ID = "Technicians"

# Initialize Firestore Client
try:
    db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)
    print("Successfully connected to Firestore.")
except Exception as e:
    print(f"Error connecting to Firestore: {e}")
    exit()

# --- Data to be added ---
technicians_data = [
    {
        "id": "alice-johnson",
        "data": {
            "technician_name": "Alice Johnson",
            "field_of_expertise": ["networking", "hardware"],
            "ticket_id": None,
            "last_assigned_time": None,
            "tickets_completed": 28,
            "tickets_reopened": 3,
            "avg_customer_satisfaction": 4.7
        }
    },
    {
        "id": "bob-williams",
        "data": {
            "technician_name": "Bob Williams",
            "field_of_expertise": ["software", "databases"],
            "ticket_id": None,
            "last_assigned_time": None,
            "tickets_completed": 42,
            "tickets_reopened": 1,
            "avg_customer_satisfaction": 4.9
        }
    },
    {
        "id": "charlie-brown",
        "data": {
            "technician_name": "Charlie Brown",
            "field_of_expertise": ["cybersecurity"],
            "ticket_id": "TICKET-54321",  # Example of a busy technician
            "last_assigned_time": firestore.SERVER_TIMESTAMP,
            "tickets_completed": 58,
            "tickets_reopened": 8,
            "avg_customer_satisfaction": 4.4
        }
    },
    {
        "id": "diana-prince",
        "data": {
            "technician_name": "Diana Prince",
            "field_of_expertise": ["cloud_services", "software"],
            "ticket_id": None,
            "last_assigned_time": None,
            "tickets_completed": 35,
            "tickets_reopened": 2,
            "avg_customer_satisfaction": 4.8
        }
    }
]

def add_technicians():
    """
    Adds predefined technician data to the Firestore collection.
    It uses the 'id' from the data as the document ID.
    """
    print(f"Starting to add technicians to '{COLLECTION_ID}' collection...")
    technicians_collection = db.collection(COLLECTION_ID)
    
    for tech in technicians_data:
        doc_id = tech["id"]
        tech_data = tech["data"]
        
        doc_ref = technicians_collection.document(doc_id)
        
        try:
            doc_ref.set(tech_data)
            print(f"  - Successfully added/updated technician: {doc_id}")
        except Exception as e:
            print(f"  - Error adding technician {doc_id}: {e}")

if __name__ == "__main__":
    add_technicians()
    print("Script finished.")
