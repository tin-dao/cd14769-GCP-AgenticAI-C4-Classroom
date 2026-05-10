import logging
import os
from google.adk.agents import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.sessions import InMemorySessionService

# Configure short-term session to use the in-memory service
session_service = InMemorySessionService()

# Read the instructions from a file in the same
# directory as this agent.py file.
script_dir = os.path.dirname(os.path.abspath(__file__))
instruction_file_path = os.path.join(script_dir, "agent-prompt.txt")
with open(instruction_file_path, "r") as f:
  instruction = f.read()

# Set up the tools that we will be using for the root agent
tools=[
]

# Define the remote A2A agent for deposit
# Assuming the deposit agent is running on 127.0.0.1:8000/a2a/deposit
deposit_agent = RemoteA2aAgent(
  name="deposit_agent",
  agent_card=f"http://127.0.0.1:8000/a2a/deposit{AGENT_CARD_WELL_KNOWN_PATH}"
)

# Define the remote A2A agent for loan
# Assuming the loan agent is running on 127.0.0.1:8000/a2a/loan
loan_agent = RemoteA2aAgent(
  name="loan_agent",
  agent_card=f"http://127.0.0.1:8000/a2a/loan{AGENT_CARD_WELL_KNOWN_PATH}"
)

# Set up other agents that we can delegate to
sub_agents=[
  deposit_agent,
  loan_agent
]

# Use the Gemini 2.5 Flash model since it performs quickly
# and handles the processing well.
model = "gemini-2.5-flash"

# Create our agent
root_agent = Agent(
  name="bank_agent",
  description="Bank agent orchestrator.",
  instruction=instruction,
  model=model,
  tools=tools,
  sub_agents=sub_agents,
)
