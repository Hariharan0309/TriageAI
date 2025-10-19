from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext
from google.cloud import firestore
import datetime

# Initialize the Firestore client
db = firestore.Client(project="valued-mediator-461216-k7", database="triageai")

def delegate_ticket_to_technician(tool_context: ToolContext) -> dict:
    """
    Finds an available technician and assigns the current ticket to them.
    This tool queries the 'Technicians' collection for a free technician,
    updates the ticket with the technician's ID, and updates the technician's
    document with the ticket ID.
    """
    state = tool_context.state
    ticket_ids = state.get('tickets', [])

    if not ticket_ids:
        return {"error": "No tickets found in the current session."}

    current_ticket_id = state.get('working_ticket', ticket_ids[-1])

    # Find an available technician
    technicians_ref = db.collection('Technicians')
    available_technicians = technicians_ref.where('ticket_id', '==', None).limit(1).stream()

    technician_doc = next(available_technicians, None)

    if not technician_doc:
        return {"error": "No technicians are currently available."}

    technician_id = technician_doc.id
    
    ticket_ref = db.collection('tickets').document(current_ticket_id)
    technician_ref = technicians_ref.document(technician_id)
    
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    try:
        # Use a transaction to ensure atomicity
        @firestore.transactional
        def update_in_transaction(transaction, ticket_ref, technician_ref):
            # Update ticket
            transaction.update(ticket_ref, {
                'assigned_technician_id': technician_id,
                'status': 'assigned',
                'last_update_time': now_utc
            })
            # Update technician
            transaction.update(technician_ref, {
                'ticket_id': current_ticket_id,
                'last_assigned_time': now_utc
            })

        transaction = db.transaction()
        update_in_transaction(transaction, ticket_ref, technician_ref)
        
        return {"success": f"Ticket {current_ticket_id} has been assigned to technician {technician_id}."}
    except Exception as e:
        return {"error": f"Failed to delegate ticket: {str(e)}"}

delegation_agent = Agent(
    name="delegation_agent",
    model="gemini-2.5-pro",
    description="Agent for delegating tickets to human technicians.",
    instruction="""You are a delegation agent. Your only job is to delegate the current IT support ticket to a human technician when requested.
    Use the `delegate_ticket_to_technician` tool to perform the delegation.""",
    tools=[delegate_ticket_to_technician],
)