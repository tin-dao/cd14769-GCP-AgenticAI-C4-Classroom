import os
import json
from typing import AsyncGenerator
from pydantic import BaseModel, Field
from google.adk.agents import SequentialAgent, ParallelAgent, LlmAgent, BaseAgent, InvocationContext
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.events import Event, EventActions
from google.genai.types import Content, Part
from toolbox_core import ToolboxSyncClient
from .datastore import datastore_search_tool


model = "gemini-2.5-flash"

def load_instructions( prompt_file: str ):
  script_dir = os.path.dirname(os.path.abspath(__file__))
  instruction_file_path = os.path.join( script_dir, prompt_file )
  with open(instruction_file_path, "r") as f:
    return f.read()

# --- Schemas ---
class LoanRequestOutput(BaseModel):
  loan_type: str = Field(description="The type of loan requested.")
  loan_amount: float = Field(description="The amount of loan requested.")

class OutstandingBalanceOutput(BaseModel):
  total_outstanding_balance: float = Field(description="The total outstanding balance on all of the customer's loans.")

class LoanCriteriaOutput(BaseModel):
  debt_to_equity_ratio: int = Field(description="The debt-to-equity ratio required for the requested loan.")
  customer_rating_required: str = Field(description="The customer rating required for the requested loan.")

class UserProfileOutput(BaseModel):
  user_rating: str = Field(description="The user rating.")

# Set up the tools that we will be using for loan approval agent
toolbox_url = os.environ.get("TOOLBOX_URL", "http://127.0.0.1:5000")
print(f"Connecting to Toolbox at {toolbox_url}")
db_client = ToolboxSyncClient( toolbox_url )

get_total_outstanding_balance_tool = db_client.load_tool("get-total-outstanding-balance")

# get_requested_value_agent
get_requested_value_agent = LlmAgent(
  name="get_requested_value_agent",
  description="Take the request from the customer and determine what type of loan they want and how much they are asking for.",
  model=model,
  instruction=load_instructions("loan-request-prompt.txt"),
  output_schema=LoanRequestOutput
)

# outstanding_balance_agent
outstanding_balance_agent = LlmAgent(
  name="outstanding_balance_agent",
  description="Get total outstanding balance on all of the customer's loans",
  model=model,
  instruction=load_instructions("outstanding-balance-prompt.txt"),
  tools=[get_total_outstanding_balance_tool],
  output_schema=OutstandingBalanceOutput
)

# policy_agent
policy_agent = LlmAgent(
  name="policy_agent",
  description="Get loan criteria based on the type and the amount the requested loan.",
  model=model,
  instruction=load_instructions("policy-prompt.txt"),
  tools=[datastore_search_tool],
  output_schema=LoanCriteriaOutput
)

class TotalValueAgent(BaseAgent):

  def __init__(
    self,
    name: str,
  ):
    super().__init__(
      name=name,
    )

  async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
    total_outstanding_balance = 0
    debt_to_equity_ratio = 1

    events = ctx.session.events
    for event in reversed(events):
      if event.author == "outstanding_balance_agent":
        try:
          # The content is expected to be a JSON string representing PlaceOrderOutput
          text = event.content.parts[0].text
          # It might be wrapped in markdown code block, clean it if necessary
          if text.startswith("```json"):
            text = text[7:-3]
          elif text.startswith("```"):
            text = text[3:-3]

          data = json.loads(text)
          total_outstanding_balance = data.get("total_outstanding_balance", 0)
          break
        except (json.JSONDecodeError, AttributeError, IndexError):
          continue
    
    for event in reversed(events):
      if event.author == "policy_agent":
        try:
          text = event.content.parts[0].text
          if text.startswith("```json"):
            text = text[7:-3]
          elif text.startswith("```"):
            text = text[3:-3]

          data = json.loads(text)
          debt_to_equity_ratio = data.get("debt_to_equity_ratio", 1)
          break
        except (json.JSONDecodeError, AttributeError, IndexError):
          continue
    
    minimum_deposit_balance = total_outstanding_balance / debt_to_equity_ratio

    yield Event(
      author=self.name,
      content=Content(
        role="assistant",
        parts=[
          Part(
            text=json.dumps({
              "minimum_deposit_balance": minimum_deposit_balance
            })
          )
        ]
      )
    )

# total_value_agent
total_value_agent = TotalValueAgent(
  name="total_value_agent"
)

# check_equity_agent
check_equity_agent = RemoteA2aAgent(
    name="check_equity_agent",
    agent_card=f"http://127.0.0.1:8000/a2a/deposit{AGENT_CARD_WELL_KNOWN_PATH}"
)

# user_profile_agent
user_profile_agent = LlmAgent(
  name="user_profile_agent",
  description="Get user rating based on user profile and bank policy.",
  model=model,
  instruction=load_instructions("user-profile-base-prompt.txt"),
  tools=[datastore_search_tool],
  output_schema=UserProfileOutput
)

# load_loan_information_agent
load_loan_information_agent = ParallelAgent(
    name="load_loan_information_agent",
    description="Load loan information, including outstanding balance, policy, and user profile in parallel.",
    sub_agents=[outstanding_balance_agent, policy_agent, user_profile_agent]
)

# check_loan_conditions_agent
check_loan_conditions_agent = SequentialAgent(
    name="check_loan_conditions_agent",
    description="Run the full loan conditions workflow: extract request, load info, and check equity.",
    sub_agents=[get_requested_value_agent, load_loan_information_agent, total_value_agent, check_equity_agent]
)

# approval_report_agent
approval_report_agent = LlmAgent(
  name="approval_report_agent",
  description="Evaluate loan conditions results and make an approval decision.",
  model=model,
  instruction=load_instructions("approval-report-prompt.txt"),
)

# loan_approval_agent
loan_approval_agent = SequentialAgent(
    name="loan_approval_agent",
    description="Full loan approval workflow: gather all conditions then evaluate for approval.",
    sub_agents=[check_loan_conditions_agent, approval_report_agent]
)
