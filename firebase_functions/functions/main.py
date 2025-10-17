from firebase_functions import https_fn, firestore_fn
from firebase_functions.options import set_global_options, MemoryOption
from firebase_admin import initialize_app, firestore, storage


import os
import vertexai
from vertexai import agent_engines
import json
import requests
from datetime import datetime

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

        response_data = json.dumps({"session_id": session_id, "state": session_state})
        return https_fn.Response(response_data, mimetype="application/json", headers=headers)

    except Exception as e:
        print(f"An error occurred in create_session: {e}")
        return https_fn.Response(f"An internal error occurred: {e}", status=500, headers=headers)