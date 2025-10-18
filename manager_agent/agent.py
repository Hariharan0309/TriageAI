from google.adk.agents import Agent

from sub_agents.ticket_management_agent import ticket_management_agent

root_agent = Agent(
    name="manager_agent",
    model="gemini-2.5-pro",
    description="Routes IT service requests to the ticket management agent.",
    instruction="""
    You are the TriageAI Manager Agent. Your only job is to receive IT service requests from users and delegate them to the `ticket_management_agent`.
    """,
    sub_agents=[
        ticket_management_agent,
    ],
)