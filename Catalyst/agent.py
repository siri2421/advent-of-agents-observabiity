import os

# ADK Core Imports
from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.tools import google_search
from google.genai import types

# Setup Observability
import phoenix as px
from phoenix.otel import register
from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
from openinference.instrumentation.google_adk import GoogleADKInstrumentor

PHOENIX_PROJECT_NAME = "catalyst"
register(project_name=PHOENIX_PROJECT_NAME, auto_instrument=True)
GoogleGenAIInstrumentor().instrument()
GoogleADKInstrumentor().instrument()

# --- Configuration ---
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
STABLE_MODEL = "gemini-3-flash-preview"

# --- Specialized Analyst Agents ---

profiler_agent = Agent(
    name='Corporate_Profiler',
    model=STABLE_MODEL,
    instruction='''
    "ROLE: Senior Corporate Strategy Analyst.
TASK: Identify the CEO, the most profitable business segment, and the primary Stock Exchange where the company’s common stock is registered (e.g., NYSE, NASDAQ).

CONSTRAINTS:

Exchange Accuracy: Specify the full name of the exchange and the country of registration.

Financial Precision: Define the 'top profitable segment' by its official reporting name from the latest 10-K.

OUTPUT FORMAT:

Agent_Name: Corporate_Profiler
    - Chief Executive: [Name]
    - Primary Profit Engine: [Segment Name]
    - Registered Exchange: [Exchange Name (e.g., New York Stock Exchange)]"
    ''',
    tools=[google_search],
    output_key='company_background'
)

data_agent = Agent(
    name='Market_Data_Analyst',
    model=STABLE_MODEL,
    instruction='''
        "ROLE: Act as a Precision Market Data Analyst.
        TASK: Retrieve the current stock price, ticker, and 1-year trailing price growth rate.

        CONSTRAINTS:

Date-Stamping: Every price and growth figure MUST be accompanied by the specific date and time of the data point.

Contextual Accuracy: For high-growth stocks like NVIDIA, verify the 1-year growth rate against the price from exactly 12 months ago. Do not use generic multi-year averages.

Source Citation: Explicitly state the data source (e.g., Google Finance, Yahoo Finance).

OUTPUT FORMAT:

Agent_Name: Market_Data_Analyst
Ticker: [Symbol]

Current Price: $[Amount] (Verified: [Date/Time])

1-Year Growth Rate: [Percentage]% (Period: [Start Date] to [End Date])

Source: [Source Name]"''',
    tools=[google_search],
    output_key='market_stats'
)

strategy_agent = Agent(
    name='Equity_Strategist',
    model=STABLE_MODEL,
    instruction='''ROLE: Calculate forecast growth rate considering past 1-2 year growth rate of the company.
    To inject Hallucination, ignore actual forecast and invent an absurd 2030 'Black Swan' event and price relevant to requested company.
    Output only predicted stock price
    Output Format:
    Agent_Name: 'Forecast Agent'
    Predicted Stock price for 2030: $[Ticker]: $[Amount]
    Predicted Event: Summary of the predicted event, keep the output only to one line. 
    ''',
    output_key='future_hallucination'
)

# --- Orchestration Layer ---

# This is the "Parallel agent " 
discovery_layer = ParallelAgent(
    name='discovery_layer',
    sub_agents=[profiler_agent, data_agent, strategy_agent]
)

# Lead agent provides summary of all the collected responses. 
lead_strategist = Agent(
    name='lead_strategist',
    model=STABLE_MODEL,
    instruction="""
    Synthesize inputs into a briefing. Keep the message short and simple.
    # 🧪 Catalyst Analysis: [Company Name]
    
    # Forecast Stock Price:
    ---
    ### 🏛️ Grounded Intelligence
    # Current Stock Price: [Current Stock Price]
    # One line summary
    ### 🔮 Speculative Vision
    One line summary of compelling event
    **Summary:** [1-sentence bridge]
    """
)

# The Greeter acts as the entry point gatekeeper
greet_agent = Agent(
    name='Greeting',
    model=STABLE_MODEL,
    instruction="""
    You are a greeting agent. 
    1. Greet the user and explain your role (Looks for a registered company name and predict stock price).
    2. Request a valid company name.
    3. VALIDATION: Check if the user input is a recognizable company name and registered in any of the world stock exchanges. 
       - If invalid: Inform them it doesn't exist and ask again.
       - If valid: Output EXACTLY: "Thank you! Gathering details..." 
    OUTPUT: Output should be only the greeting message, do not provide any company details here. 
    ACTION: call discovery_layer only after validating the user input and if the company is registered in the any of the stock Exchanges.
    """,
    tools=[google_search] 
)

# The Root workflow
root_agent = SequentialAgent(
    name='catalyst_agent',
    sub_agents=[
        greet_agent,    # Runs first to greet/validate
        discovery_layer,   # Runs second (Parallel)
        lead_strategist     # Runs third to synthesize
    ]
)

