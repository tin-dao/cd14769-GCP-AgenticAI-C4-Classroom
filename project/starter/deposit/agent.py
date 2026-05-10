import os
from pydantic import BaseModel, Field
from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService

from toolbox_core import ToolboxSyncClient

# Configure short-term session to use the in-memory service
session_service = InMemorySessionService()

# Read the instructions from a file in the same
# directory as this agent.py file.
script_dir = os.path.dirname(os.path.abspath(__file__))
instruction_file_path = os.path.join(script_dir, "agent-prompt.txt")
with open(instruction_file_path, "r") as f:
  instruction = f.read()

# Schema for minimum deposit balance check tool
class DepositBalanceCheckOutput(BaseModel):
  deposit_balance_sufficient: bool = Field(description="True if the user has sufficient deposit balance, False otherwise.")

# Set up the tools that we will be using for the root agent
toolbox_url = os.environ.get("TOOLBOX_URL", "http://127.0.0.1:5000")
print(f"Connecting to Toolbox at {toolbox_url}")
db_client = ToolboxSyncClient( toolbox_url )

get_account_balance_tool = db_client.load_tool("get-account-balance")
list_accounts_tool = db_client.load_tool("list-accounts")
get_transaction_details_tool = db_client.load_tool("get-transaction-details")
get_last_payment_tool = db_client.load_tool("get-last-payment")
check_deposit_sufficient_tool = db_client.load_tool("check-deposit-sufficient")

tools=[
  get_account_balance_tool,
  list_accounts_tool,
  get_transaction_details_tool,
  get_last_payment_tool,
  check_deposit_sufficient_tool
]

# Use the Gemini 2.5 Flash model since it performs quickly
# and handles the processing well.
model = "gemini-2.5-flash"

# Create our agent
root_agent = Agent(
  name="deposit_agent",
  description="Handles questions about deposit accounts and balances.",
  model=model,
  instruction=instruction,
  tools=tools,
)