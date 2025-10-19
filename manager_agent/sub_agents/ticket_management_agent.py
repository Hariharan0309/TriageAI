from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext
from google.cloud import firestore
import uuid
from datetime import datetime
from .analysis_agent import analysis_agent

# Initialize the Firestore client
db = firestore.Client(project="valued-mediator-461216-k7", database="triageai")

def create_ticket(user_query: str, tool_context: ToolContext) -> str:
    """Creates a ticket in Firestore and stores the ticket ID in the session state.

    Args:
        user_query: The user's query describing the issue.

    Returns:
        The unique ID of the created ticket.
    """
    state = tool_context.state
    user_id = state.get('user_id')

    if not user_id:
        # This should not happen if the session service is configured correctly
        return "Error: user_id not found in session state."

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

    return ticket_id


ticket_management_agent = Agent(
    name="ticket_management_agent",
    model="gemini-2.5-pro",
    description="Agent for managing and creating support tickets, and routing to analysis.",
    instruction="""You are a router agent. Your purpose is to manage the first step of an IT support request.

    **Your workflow is fixed and you must follow it exactly:**

    1.  Examine the user's request.
    2.  Check if a ticket has already been created in this conversation.
    3.  If no ticket has been created, you **must** use the `create_ticket` tool.
    4.  After a ticket has been created, or if a ticket already existed, you **must** delegate the task to the `analysis_agent`.

    You **must not** respond directly to the user. Your only job is to use the `create_ticket` tool if needed, and then delegate to the `analysis_agent`.
    """,
    tools=[create_ticket],
    sub_agents=[analysis_agent],
)