# Multi-Agent Banking System Report

## Multi-Agent Architecture
The system employs a hierarchical multi-agent architecture designed to separate concerns and enforce domain boundaries.
- **Bank Manager Agent (Orchestrator)**: The primary entry point for user interactions. It analyzes the user's intent and routes the query to either the `deposit_agent` or the `loan_agent`.
- **Deposit Agent**: Specialized in handling deposit account balances, listing accounts, fetching transaction history, and performing deposit sufficiency checks using internal database tools (including `check_deposit_sufficient_tool`).
- **Loan Agent**: Specialized in loan inquiries (balance checks) and delegating loan applications to the `loan_approval_agent`.
- **Loan Approval Agent**: A `SequentialAgent` that orchestrates the full loan approval workflow by first gathering all loan conditions data, then passing control to the `approval_report_agent` for the final decision.

## Loan Approval Orchestration
When a user requests a new loan, the `loan_agent` delegates the task to the `loan_approval_agent`. This agent is a `SequentialAgent` that runs two stages:

### Stage 1: Data Gathering (`check_loan_conditions_agent`)
A `SequentialAgent` that executes the following pipeline:
1. **`get_requested_value_agent`**: Extracts the requested loan type and amount from the user's natural language input.
2. **`load_loan_information_agent`**: A `ParallelAgent` that concurrently runs:
   - `outstanding_balance_agent`: Fetches the customer's total outstanding debt.
   - `policy_agent`: Retrieves the bank's lending policy (e.g., required debt-to-equity ratio, required customer rating) from the datastore.
   - `user_profile_agent`: Evaluates the customer's profile to determine their rating.
3. **`total_value_agent`**: A custom `BaseAgent` that computes the required minimum deposit balance using the formula: `total_outstanding_balance / debt_to_equity_ratio`.
4. **`check_equity_agent`**: A `RemoteA2aAgent` that securely calls the `deposit_agent` via A2A protocol to verify if the user's actual deposit balances meet or exceed the required minimum.

### Stage 2: Decision (`approval_report_agent`)
An `LlmAgent` that reviews the full conversation history from all agents in Stage 1 and makes the final determination. It evaluates two criteria:
- **Equity sufficiency**: The `check_equity_agent` result must indicate sufficient deposit balance.
- **User rating**: The `user_profile_agent` rating must meet or exceed the `policy_agent` threshold.

The loan is approved only if **both** conditions are met. The agent generates a customer-friendly response without revealing any internal policy details or user ratings.

### Key Architectural Decision
The `approval_report_agent` is a **sibling** of `check_loan_conditions_agent` inside the parent `SequentialAgent`, rather than a parent that delegates to a sub-agent. This design avoids a critical ADK framework behavior: when an `LlmAgent` transfers control to a sub-agent, the sub-agent's final output becomes the response and the LLM never re-evaluates. By making them siblings in a `SequentialAgent`, the data-gathering pipeline is guaranteed to complete before the evaluator runs.

## Deposit Agent Design
The deposit agent consolidates all database tools—including `check_deposit_sufficient_tool`—directly on the root agent, avoiding unnecessary sub-agent delegation. When it receives a `minimum_deposit_balance` request from the loan pipeline (via A2A), it extracts the value, calls the tool, and returns a structured `<INTERNAL_CHECK>` JSON response. For regular user queries, it behaves as a standard deposit account assistant.

## Evaluation of Test Results
Based on the test results:

### Strengths
- **Accurate routing and entity extraction**: In `thread-001`, the system correctly identifies the "vacation account" and returns the precise balance ($1,500.00). In `thread-002`, it appropriately asks for clarification before returning the primary account balance ($5,230.50).
- **Correct loan approval logic**: In `thread-007`, a $100 "bubble gum" loan is correctly approved (low amount, sufficient equity), while the follow-up $10,000 request in the same thread is correctly rejected. In `thread-009`, a $500,000 mortgage is accurately rejected due to insufficient funds. In `thread-010`, a $10,000 auto loan is correctly approved.
- **No policy leakage in loan decisions**: Responses are general and customer-friendly (e.g., `thread-008`: "Great news! ... your request for a $700 loan has been approved" without mentioning internal criteria).
- **Proper boundary enforcement**: In `thread-006`, the system correctly refuses to perform deposit operations (adding funds).

### Areas for Improvement
- **Multi-intent queries**: In `thread-015`, when asked about total balances across accounts *and* loans, the manager routed only to the `deposit_agent`, which returned deposit balances but stated it could not provide loan information. The manager should dispatch to both agents and synthesize results.
- **Ambiguous last payment lookup**: In `thread-004`, the query "most recent payment on my main account" returned "I couldn't find your last payment," likely due to the `get_last_payment_tool` not matching "main" to "primary" account type.
- **Outstanding loans enumeration**: In `thread-013`, the system asks for loan type instead of listing all outstanding loans, indicating the `get_loan_balance_tool` may not support listing all loans without a type parameter.

## Risks in Banking Applications
1. **LLM Hallucinations and Prompt Leaks**: LLMs can ignore negative constraints under adversarial prompting. In banking, inadvertently exposing internal risk formulas, user profile ratings, or policy thresholds is a severe compliance and security risk.
2. **Poor Edge Case Routing**: Relying on an LLM to route multi-intent queries can lead to incomplete answers. If a multi-part question is routed to only one specialist, the customer receives partial or incorrect information.
3. **Remote Agent Trust**: The `check_equity_agent` communicates with the deposit agent via A2A. If the remote agent returns unexpected data formats or errors, the pipeline may produce incorrect approval decisions.

## Mitigations
1. **Output Guardrails**: Implement strict output verification. A separate "Guardrail Agent" or deterministic regex filter should scrub the final output for internal terminology (e.g., "debt-to-equity", "customer rating", specific ratio values) before it reaches the customer.
2. **Multi-Intent Planners**: Upgrade the Manager Agent to use a plan-and-execute framework. If a query contains multiple intents, the planner should break it down, dispatch calls to both the `deposit_agent` and `loan_agent`, and synthesize the combined results.

## Future System Improvements
1. **Implement a Dedicated Guardrail Layer**: Add an interceptor at the gateway level that validates both inputs (for prompt injection) and outputs (for policy leakage) to ensure banking compliance.
2. **Enhanced State Management**: Introduce a robust state tracking mechanism so that follow-up questions (like "In that case, can I get $10000?") are explicitly linked to the prior extracted loan context, rather than relying on raw conversation history which can confuse specialized agents.
3. **Comprehensive Loan Inquiry Support**: Extend the `loan_agent` to support listing all outstanding loans and providing aggregate loan summaries without requiring a specific loan type.
