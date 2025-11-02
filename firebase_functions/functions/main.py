from firebase_functions import https_fn, firestore_fn
from firebase_functions.options import set_global_options, MemoryOption
from firebase_admin import initialize_app, firestore, storage


import os
import vertexai
from vertexai import agent_engines
import json
import requests
from datetime import datetime
from vertexai.generative_models import Content, Part

# --- Configuration ---
PROJECT_ID = os.environ.get("GCP_PROJECT", "valued-mediator-461216-k7")
LOCATION = os.environ.get("FUNCTION_REGION", "us-central1")
REASONING_ENGINE_ID = os.environ.get("REASONING_ENGINE_ID", "2064957603754016768")
DATABASE = "triageai"


# Firestore Configuration
SESSIONS_COLLECTION = "adk_sessions"
# --------------------

# --- Initialization ---
initialize_app()
set_global_options(max_instances=10, memory=MemoryOption.GB_1, timeout_sec=660)

_remote_app = None

def get_remote_app():
    global _remote_app
    if _remote_app is None:
        print("Initializing Vertex AI client...")
        engine_resource_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{REASONING_ENGINE_ID}"
        _remote_app = agent_engines.get(engine_resource_name)
        print("Vertex AI client initialized.")
    return _remote_app

@https_fn.on_request()
def TriageAI_Login(req: https_fn.Request) -> https_fn.Response:
    """
    HTTP Cloud Function to generate investment analysis, now with CORS support.
    """
    # Set CORS headers for the preflight OPTIONS request.
    if req.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        }
        return https_fn.Response("", headers=headers, status=204)

    # Set CORS headers for the main request.
    headers = {
        "Access-Control-Allow-Origin": "*",
    }
    try:
        request_json = req.get_json(silent=True)
        if not request_json or 'user_id' not in request_json:
            return https_fn.Response("Error: Please provide 'user_id' in the JSON body.", status=400, headers=headers)
        
        user_id = request_json['user_id']
        initial_state = request_json.get('state', {})
        remote_app = get_remote_app()

        print(f"Checking for existing sessions for user '{user_id}'...")
        list_sessions_response = remote_app.list_sessions(user_id=user_id)
        
        session_id = None
        session_state = {}

        if list_sessions_response and list_sessions_response.get('sessions'):
            remote_session = list_sessions_response['sessions'][0]
            session_id = remote_session.get('id')
            session_state = remote_session.get('state', {})
            print(f"Found existing session with ID: {session_id}")
        else:
            print(f"No existing sessions for user '{user_id}'. Creating a new one.")
            new_session = remote_app.create_session(user_id=user_id, state=initial_state)
            session_id = new_session.get('id')
            session_state = new_session.get('state', {})
            print(f"Created new session with ID: {session_id}")
        
        if not session_id:
             raise Exception("Failed to get or create a session ID.")

        tickets_info = []
        if 'tickets' in session_state and session_state['tickets']:
            db = firestore.Client(project="valued-mediator-461216-k7", database="triageai")
            for ticket_id in session_state['tickets']:
                ticket_ref = db.collection('tickets').document(ticket_id)
                ticket_doc = ticket_ref.get()
                if ticket_doc.exists:
                    ticket_data = ticket_doc.to_dict()
                    if 'last_update_time' in ticket_data and hasattr(ticket_data['last_update_time'], 'isoformat'):
                        ticket_data['last_update_time'] = ticket_data['last_update_time'].isoformat()
                    tickets_info.append(ticket_data)

        response_data_dict = {"session_id": session_id, "state": session_state}
        if tickets_info:
            response_data_dict['tickets'] = tickets_info
        
        response_data = json.dumps(response_data_dict)
        return https_fn.Response(response_data, mimetype="application/json", headers=headers)

    except Exception as e:
        print(f"An error occurred in create_session: {e}")
        return https_fn.Response(f"An internal error occurred: {e}", status=500, headers=headers)

@https_fn.on_request()
def raise_query(req: https_fn.Request) -> https_fn.Response:
    """
    HTTP Cloud Function to send a query to the agent and retrieve its response and updated session state.
    """
    # Set CORS headers for the preflight OPTIONS request.
    if req.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        }
        return https_fn.Response("", headers=headers, status=204)

    # Set CORS headers for the main request.
    headers = {
        "Access-Control-Allow-Origin": "*",
    }
    try:
        request_json = req.get_json(silent=True)
        if not request_json or 'user_query' not in request_json or 'session_id' not in request_json or 'user_id' not in request_json:
            return https_fn.Response("Error: Please provide 'user_query', 'session_id', and 'user_id' in the JSON body.", status=400, headers=headers)

        user_query = request_json['user_query']
        session_id = request_json['session_id']
        user_id = request_json['user_id']

        remote_app = get_remote_app()

        # Get the session state before the query
        initial_session = remote_app.get_session(user_id=user_id, session_id=session_id)
        initial_state = initial_session.get('state', {})
        initial_tickets = set(initial_state.get('tickets', []))

        # Construct message for the agent
        from vertexai.generative_models import Content, Part
        final_message = Content(parts=[Part.from_text(user_query)], role="user").to_dict()

        print(f"Streaming query to agent for session '{session_id}'...")
        response_chunks = []
        for event in remote_app.stream_query(user_id=user_id, session_id=session_id, message=final_message):
            if event.get('content') and event.get('content').get('parts'):
                for part in event['content']['parts']:
                    if part.get('text'):
                        response_chunks.append(part['text'])

        full_response_text = "".join(response_chunks)
        print(f"Agent response: {full_response_text}")

        # Get the updated session state
        updated_session = remote_app.get_session(user_id=user_id, session_id=session_id)
        updated_state = updated_session.get('state', {})
        updated_tickets = set(updated_state.get('tickets', []))

        new_ticket_ids = updated_tickets - initial_tickets
        new_ticket_info = None
        if new_ticket_ids:
            new_ticket_id = new_ticket_ids.pop()
            db = firestore.Client(project="valued-mediator-461216-k7", database="triageai")
            ticket_ref = db.collection('tickets').document(new_ticket_id)
            ticket_doc = ticket_ref.get()
            if ticket_doc.exists:
                new_ticket_info = ticket_doc.to_dict()
                if 'last_update_time' in new_ticket_info and hasattr(new_ticket_info['last_update_time'], 'isoformat'):
                    new_ticket_info['last_update_time'] = new_ticket_info['last_update_time'].isoformat()

        if new_ticket_info and 'interaction_id' in new_ticket_info:
            interaction_id = new_ticket_info['interaction_id']
            db = firestore.Client(project="valued-mediator-461216-k7", database="triageai")
            interaction_ref = db.collection('interactions').document(interaction_id)
            agent_message = {
                "author": "agent",
                "content": full_response_text,
                "timestamp": datetime.now(),
            }
            interaction_ref.update({"messages": firestore.ArrayUnion([agent_message])})

        response_data_dict = {
            "agent_response": full_response_text,
            "session_state": updated_state
        }
        if new_ticket_info:
            response_data_dict['new_ticket'] = new_ticket_info
        
        response_data = json.dumps(response_data_dict)
        return https_fn.Response(response_data, mimetype="application/json", headers=headers)

    except Exception as e:
        print(f"An error occurred in raise_query: {e}")
        return https_fn.Response(f"An internal error occurred: {e}", status=500, headers=headers)

@https_fn.on_request()
def interact(req: https_fn.Request) -> https_fn.Response:
    """
    HTTP Cloud Function to interact with the agent about a specific ticket.
    """
    # Set CORS headers
    if req.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        }
        return https_fn.Response("", headers=headers, status=204)

    headers = {
        "Access-Control-Allow-Origin": "*",
    }

    try:
        request_json = req.get_json(silent=True)
        if not request_json or not all(k in request_json for k in ['ticket_id', 'user_id', 'session_id', 'user_query']):
            return https_fn.Response("Error: Please provide 'ticket_id', 'user_id', 'session_id', and 'user_query' in the JSON body.", status=400, headers=headers)

        ticket_id = request_json['ticket_id']
        user_id = request_json['user_id']
        session_id = request_json['session_id']
        user_query = request_json['user_query']
        status = request_json.get('status')

        db = firestore.Client(project="valued-mediator-461216-k7", database="triageai")

        # Get the interaction_id from the ticket
        ticket_ref = db.collection('tickets').document(ticket_id)
        ticket_doc = ticket_ref.get()
        if not ticket_doc.exists:
            return https_fn.Response(f"Error: Ticket with ID {ticket_id} not found.", status=404, headers=headers)
        
        interaction_id = ticket_doc.to_dict().get('interaction_id')
        if not interaction_id:
            return https_fn.Response(f"Error: Interaction ID not found for ticket {ticket_id}.", status=500, headers=headers)

        interaction_ref = db.collection('interactions').document(interaction_id)

        # Save user's query
        user_message = {
            "author": "user",
            "content": user_query,
            "timestamp": datetime.now(),
        }
        interaction_ref.update({"messages": firestore.ArrayUnion([user_message])})

        if status == "assigned":
            response_data = json.dumps({
                "agent_response": ""
            })
            return https_fn.Response(response_data, mimetype="application/json", headers=headers)

        # Update the working_ticket in the session state
        session_ref = db.collection(SESSIONS_COLLECTION).document(session_id)
        session_ref.update({"state.working_ticket": ticket_id})

        # Formulate the prompt
        prompt = f"For ticket {ticket_id}, answer this query: {user_query}"

        remote_app = get_remote_app()

        # Construct message for the agent
        final_message = Content(parts=[Part.from_text(prompt)], role="user").to_dict()

        print(f"Streaming query to agent for session '{session_id}' about ticket '{ticket_id}'...")
        response_chunks = []
        for event in remote_app.stream_query(user_id=user_id, session_id=session_id, message=final_message):
            if event.get('content') and event.get('content').get('parts'):
                for part in event['content']['parts']:
                    if part.get('text'):
                        response_chunks.append(part['text'])

        full_response_text = "".join(response_chunks)
        print(f"Agent response: {full_response_text}")

        # Save agent's response
        agent_message = {
            "author": "agent",
            "content": full_response_text,
            "timestamp": datetime.now(),
        }
        interaction_ref.update({"messages": firestore.ArrayUnion([agent_message])})

        if 'timestamp' in agent_message and hasattr(agent_message['timestamp'], 'isoformat'):
            agent_message['timestamp'] = agent_message['timestamp'].isoformat()

        response_data = json.dumps({
            "agent_response": agent_message
        })
        return https_fn.Response(response_data, mimetype="application/json", headers=headers)

    except Exception as e:
        print(f"An error occurred in interact: {e}")
        return https_fn.Response(f"An internal error occurred: {e}", status=500, headers=headers)

@https_fn.on_request()
def get_interaction_history(req: https_fn.Request) -> https_fn.Response:
    """
    HTTP Cloud Function to get the interaction history for a specific interaction ID.
    """
    # Set CORS headers
    if req.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        }
        return https_fn.Response("", headers=headers, status=204)

    headers = {
        "Access-Control-Allow-Origin": "*",
    }

    try:
        request_json = req.get_json(silent=True)
        if not request_json or 'interaction_id' not in request_json:
            return https_fn.Response("Error: Please provide 'interaction_id' in the JSON body.", status=400, headers=headers)

        interaction_id = request_json['interaction_id']

        db = firestore.Client(project="valued-mediator-461216-k7", database="triageai")

        # Get the interaction history
        interaction_ref = db.collection('interactions').document(interaction_id)
        interaction_doc = interaction_ref.get()
        if not interaction_doc.exists:
            return https_fn.Response(f"Error: Interaction history not found for interaction ID {interaction_id}.", status=404, headers=headers)

        interaction_data = interaction_doc.to_dict()

        # Convert timestamps to strings
        if 'messages' in interaction_data:
            for message in interaction_data['messages']:
                if 'timestamp' in message and hasattr(message['timestamp'], 'isoformat'):
                    message['timestamp'] = message['timestamp'].isoformat()

        response_data = json.dumps(interaction_data)
        return https_fn.Response(response_data, mimetype="application/json", headers=headers)

    except Exception as e:
        print(f"An error occurred in get_interaction_history: {e}")
        return https_fn.Response(f"An internal error occurred: {e}", status=500, headers=headers)

@https_fn.on_request()
def technician_login(req: https_fn.Request) -> https_fn.Response:
    """
    HTTP Cloud Function to add or retrieve a technician and retrieve ticket information.
    """
    # Set CORS headers
    if req.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        }
        return https_fn.Response("", headers=headers, status=204)

    headers = {
        "Access-Control-Allow-Origin": "*",
    }

    try:
        request_json = req.get_json(silent=True)
        if not request_json or 'technician_id' not in request_json:
            return https_fn.Response("Error: Please provide 'technician_id' in the JSON body.", status=400, headers=headers)

        technician_id = request_json['technician_id']

        db = firestore.Client(project="valued-mediator-461216-k7", database="triageai")

        # Check if technician exists
        technician_ref = db.collection('Technicians').document(technician_id)
        technician_doc = technician_ref.get()
        ticket_data = {}

        if technician_doc.exists:
            technician_data = technician_doc.to_dict()
            ticket_id = technician_data.get('ticket_id')
            if ticket_id:
                ticket_ref = db.collection('tickets').document(ticket_id)
                ticket_doc = ticket_ref.get()
                if ticket_doc.exists:
                    ticket_data = ticket_doc.to_dict()
        else:
            # Create new technician
            technician_data = {
                "technician_name": request_json.get('technician_name'),
                "field_of_expertise": request_json.get('field_of_expertise'),
                "ticket_id": None,
                "last_assigned_time": None,
                "tickets_completed": 0,
                "tickets_reopened": 0,
                "avg_customer_satisfaction": 0,
                "created_at": datetime.now(),
            }
            technician_ref.set(technician_data)

        # Convert timestamps to strings
        if 'created_at' in technician_data and hasattr(technician_data['created_at'], 'isoformat'):
            technician_data['created_at'] = technician_data['created_at'].isoformat()

        if 'last_assigned_time' in technician_data and hasattr(technician_data['last_assigned_time'], 'isoformat'):
            technician_data['last_assigned_time'] = technician_data['last_assigned_time'].isoformat()
        
        if 'last_update_time' in ticket_data and hasattr(ticket_data['last_update_time'], 'isoformat'):
            ticket_data['last_update_time'] = ticket_data['last_update_time'].isoformat()

        response_data = json.dumps({
            "technician": technician_data,
            "ticket": ticket_data,
        })
        return https_fn.Response(response_data, mimetype="application/json", headers=headers)

    except Exception as e:
        print(f"An error occurred in technician_login: {e}")
        return https_fn.Response(f"An internal error occurred: {e}", status=500, headers=headers)

@https_fn.on_request()
def technician_interact(req: https_fn.Request) -> https_fn.Response:
    """
    HTTP Cloud Function to handle interactions with technicians.
    """
    # Set CORS headers
    if req.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        }
        return https_fn.Response("", headers=headers, status=204)

    headers = {
        "Access-Control-Allow-Origin": "*",
    }

    try:
        request_json = req.get_json(silent=True)
        if not request_json or not all(k in request_json for k in ['technician_id', 'message', 'interaction_id']):
            return https_fn.Response("Error: Please provide 'technician_id', 'message', and 'interaction_id' in the JSON body.", status=400, headers=headers)

        technician_id = request_json['technician_id']
        message = request_json['message']
        interaction_id = request_json['interaction_id']

        db = firestore.Client(project="valued-mediator-461216-k7", database="triageai")

        interaction_ref = db.collection('interactions').document(interaction_id)

        # Save technician's message
        technician_message = {
            "author": technician_id,
            "content": message,
            "timestamp": datetime.now(),
        }
        interaction_ref.update({"messages": firestore.ArrayUnion([technician_message])})

        response_data = json.dumps({
            "status": "success",
            "message": "Message added to interaction."
        })
        return https_fn.Response(response_data, mimetype="application/json", headers=headers)

    except Exception as e:
        print(f"An error occurred in technician_interact: {e}")
        return https_fn.Response(f"An internal error occurred: {e}", status=500, headers=headers)

@https_fn.on_request()
def close_ticket(req: https_fn.Request) -> https_fn.Response:
    """
    HTTP Cloud Function to close a ticket and update the assigned technician's data.
    """
    # Set CORS headers
    if req.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        }
        return https_fn.Response("", headers=headers, status=204)

    headers = {
        "Access-Control-Allow-Origin": "*",
    }

    try:
        request_json = req.get_json(silent=True)
        if not request_json or 'ticket_id' not in request_json:
            return https_fn.Response("Error: Please provide 'ticket_id' in the JSON body.", status=400, headers=headers)

        ticket_id = request_json['ticket_id']

        db = firestore.Client(project="valued-mediator-461216-k7", database="triageai")

        ticket_ref = db.collection('tickets').document(ticket_id)
        ticket_doc = ticket_ref.get()

        if not ticket_doc.exists:
            return https_fn.Response(f"Error: Ticket with ID {ticket_id} not found.", status=404, headers=headers)

        ticket_data = ticket_doc.to_dict()
        ticket_ref.update({"status": "closed"})

        if 'assigned_technician_id' in ticket_data and ticket_data['assigned_technician_id']:
            technician_id = ticket_data['assigned_technician_id']
            technician_ref = db.collection('Technicians').document(technician_id)
            technician_ref.update({"ticket_id": None})

        response_data = json.dumps({
            "status": "success",
            "message": f"Ticket {ticket_id} has been closed."
        })
        return https_fn.Response(response_data, mimetype="application/json", headers=headers)

    except Exception as e:
        print(f"An error occurred in close_ticket: {e}")
        return https_fn.Response(f"An internal error occurred: {e}", status=500, headers=headers)
