from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext
from google.cloud import firestore

# Initialize the Firestore client
db = firestore.Client(project="valued-mediator-461216-k7", database="triageai")

def current_ticket_information(tool_context: ToolContext) -> dict:
    """Gets the information for the current ticket from Firestore.

    Returns:
        A dictionary containing the ticket information, or an error message.
    """
    state = tool_context.state
    ticket_ids = state.get('tickets', [])

    if not ticket_ids:
        return {"error": "No tickets found in the current session."}

    # Assume the last ticket is the current one
    current_ticket_id = state.get('working_ticket', ticket_ids[-1])

    ticket_ref = db.collection('tickets').document(current_ticket_id)
    ticket_doc = ticket_ref.get()

    if not ticket_doc.exists:
        return {"error": f"Ticket with ID {current_ticket_id} not found."}

    ticket_data = ticket_doc.to_dict()
    
    # Convert timestamp to string
    if 'last_update_time' in ticket_data and hasattr(ticket_data['last_update_time'], 'isoformat'):
        ticket_data['last_update_time'] = ticket_data['last_update_time'].isoformat()
        
    return ticket_data

analysis_agent = Agent(
    name="analysis_agent",
    model="gemini-2.5-pro",
    description="Agent for analyzing user queries and providing solutions.",
    instruction="""You are an analysis agent. Your job is to analyze the user's IT issue. 
    Use the `current_ticket_information` tool to get the details of the ticket you are working on. 
    Based on the ticket information and the user's query, provide a step-by-step solution if possible. 
    If you need more information to solve the problem, ask clarifying questions to the user. 
    Be concise and clear in your solution and questions.""",
    tools=[current_ticket_information],
)