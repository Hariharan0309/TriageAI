from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext
from google.cloud import firestore
import uuid
from datetime import datetime
from .analysis_agent import analysis_agent

# Initialize the Firestore client
db = firestore.Client(project="valued-mediator-461216-k7", database="triageai")

def create_ticket(user_query: str, tool_context: ToolContext) -> dict:
    """Creates a ticket in Firestore and stores the ticket ID in the session state.

    Args:
        user_query: The user's query describing the issue.

    Returns:
        A dictionary with the ticket creation details.
    """
    state = tool_context.state
    user_id = state.get('user_id')

    if not user_id:
        # This should not happen if the session service is configured correctly
        return {"error": "user_id not found in session state."}

    # Create a new document for the interaction history
    interaction_ref = db.collection("interactions").document()
    interaction_id = interaction_ref.id
    
    # Add the initial user query to the interaction history
    initial_message = {
        "author": "user",
        "content": user_query,
        "timestamp": datetime.now(),
    }
    interaction_ref.set({"messages": [initial_message]})

    ticket_data = {
        "last_update_time": datetime.now(),
        "ticket_creator": {"user_id": user_id},
        "description": user_query,
        "status": "new",
        "technician_assigned": None,
        "interaction_id": interaction_id,
    }

    # Create a new document in the 'tickets' collection
    _, doc_ref = db.collection("tickets").add(ticket_data)
    ticket_id = doc_ref.id

    # Update the working_ticket in the session state
    state['working_ticket'] = ticket_id

    # Add the new ticket ID to the list of tickets in the state
    current_tickets = state.get('tickets', [])
    new_tickets = current_tickets + [ticket_id]
    state['tickets'] = new_tickets

    print(f"Ticket created with ID: {ticket_id} for query: {user_query}")


    return{"action": "ticket creation",
        "ticket_id": ticket_id,
        "message": f"Ticket created successfully with ID: {ticket_id}.",
        "user_query": user_query,
        }


ticket_management_agent = Agent(
    name="ticket_management_agent",
    model="gemini-2.5-pro",
    description="Agent for managing and creating support tickets, and routing to analysis.",
    instruction="""You are the TriageAI Ticket Management Agent. Your job is to handle IT service requests.

    **Workflow:**

    1.  **Analyze the user's request and the conversation history.**
    2.  **Check if a ticket has already been created for this issue in the current session.**
    3.  If the user is presenting a **new IT issue** and **no ticket has been created yet**, use the `create_ticket` tool to create a new ticket.
    4.  After checking for and creating a ticket if necessary, delegate the task to the `analysis_agent` to analyze the problem.
    """,
    tools=[create_ticket],
    sub_agents=[analysis_agent],
)
