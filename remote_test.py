import vertexai
from vertexai import agent_engines
import os
from dotenv import load_dotenv


load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")

initial_state = {
    "user_id": "technician_test_001",
}

USER_ID = "technician_test_001"
PROMPT = "what can you do?"
        


remote_app = agent_engines.get(
    f"projects/{PROJECT_ID}/locations/us-central1/reasoningEngines/2064957603754016768"
)
print(remote_app)

# Get existing sessions for the user
list_sessions_response = remote_app.list_sessions(user_id=USER_ID)
print(f"List sessions response: {list_sessions_response}")
sessions = list_sessions_response['sessions']
print(f"Found {len(sessions)} existing sessions.")
# sessions = list_sessions_response

if sessions:
    # Use the first existing session
    remote_session = sessions[0]
    print(f"Using existing session: {remote_session['id']}")
    print(f"Session state: {remote_session['state']}")
else:
    # Or create a new one if none exist
    print("No existing sessions found. Creating a new one.")
    remote_session = remote_app.create_session(user_id=USER_ID, state=initial_state)
    print(f"Created new session: {remote_session['id']}")
for event in remote_app.stream_query(
    user_id=USER_ID,
    session_id=remote_session["id"],
    message=PROMPT,
):
    print(event)