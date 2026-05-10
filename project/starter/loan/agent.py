import os
from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService
from toolbox_core import ToolboxSyncClient
from .loan import loan_approval_agent

# Configure short-term session to use the in-memory service
session_service = InMemorySessionService()

# Read the instructions from a file in the same
# directory as this agent.py file.
script_dir = os.path.dirname(os.path.abspath(__file__))
instruction_file_path = os.path.join(script_dir, "agent-prompt.txt")
with open(instruction_file_path, "r") as f:
  instruction = f.read()

# Set up the tools that we will be using for the root agent
toolbox_url = os.environ.get("TOOLBOX_URL", "http://127.0.0.1:5000")
print(f"Connecting to Toolbox at {toolbox_url}")
db_client = ToolboxSyncClient( toolbox_url )

get_loan_balance_tool = db_client.load_tool("get-loan-balance")

# Set up the tools that we will be using for the root agent
tools=[
  get_loan_balance_tool
]

sub_agents = [
  loan_approval_agent
]

# Use the Gemini 2.5 Flash model since it performs quickly
# and handles the processing well.
model = "gemini-2.5-flash"

# Create our agent
root_agent = Agent(
  name="loan_agent",
  description="Handles questions about loan accounts, loan balances and loan requests.",
  model=model,
  instruction=instruction,
  tools=tools,
  sub_agents=sub_agents
)