import os
import json
import re
from datetime import date
import pandas as pd
import phoenix as px
from phoenix.client import Client
from phoenix.evals.metrics.faithfulness import FaithfulnessEvaluator
from phoenix.evals.metrics.correctness import CorrectnessEvaluator
from phoenix.evals import evaluate_dataframe, LLM, bind_evaluator

# 1. Configuration
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
os.environ["GOOGLE_CLOUD_PROJECT"] = "ksiri-ai"
JUDGE_MODEL = "gemini-3.1-pro-preview" 
TEACHER_MODEL = "gemini-3.1-pro-preview" # Used for fetching real-time ground truth
PROJECT_NAME = "catalyst"
today = date.today()
def extract_text(val):
    """Robustly extract human-readable text from Google ADK JSON or string parts."""
    if not isinstance(val, str): return str(val)
    if "parts=[" in val and "text='" in val:
        matches = re.findall(r"text='(.*?)'", val, re.DOTALL)
        if matches: return "\n".join(matches)
    try:
        data = json.loads(val)
        if "contents" in data:
            texts = []
            for c in data["contents"]:
                if isinstance(c, str):
                    m = re.search(r"text='(.*?)'", c, re.DOTALL)
                    texts.append(m.group(1) if m else c)
                elif isinstance(c, dict):
                    for p in c.get("parts", []):
                        if isinstance(p, dict) and "text" in p: texts.append(p["text"])
            return "\n".join(texts)
        if "candidates" in data:
            c = data["candidates"][0]
            p = c.get("content", {}).get("parts", [])
            if p and isinstance(p, list):
                if isinstance(p[0], dict) and "text" in p[0]: return p[0]["text"]
                elif isinstance(p[0], str): return p[0]
    except: pass
    return val

def get_real_time_ground_truth(row):
    """Teacher LLM: Uses search/tools to find the 'True' answer to compare against the agent."""
    input_text = row["text_input"]
    
    # Custom instructions for the Forecasting Agent Ground Truth
    if "[forecasting_agent]" in input_text:
        teacher_llm = LLM(provider="google", model=TEACHER_MODEL)
        
        # We prompt the Teacher to find actual historical data and a realistic forecast
        prompt = (
            f"Today is {today}. Research real-time data for: {input_text}. "
            f"Research real-time data for the following request: {input_text}. "
            f"Calculate forecast growth rate considering past growth rate of the company. "
            f"Provide a factual reference answer containing the ticker, actual current price, "
            f"and a realistic 2030 projection based on public financial analysis."
        )
        # Note: In a production environment, ensure the teacher has tools/search enabled.
        return teacher_llm.confirm_and_generate(prompt)
    
    return "No reference needed"

def run_hallucination_check():
    px_client = Client()
    print(f"--- Fetching traces from project: {PROJECT_NAME} ---")
    df = px_client.spans.get_spans_dataframe(project_name=PROJECT_NAME)
    if df.empty:
        print("❌ ERROR: No traces found.")
        return

    # Filter and Clean
    eval_df = df[df["span_kind"] == "LLM"].copy()
    eval_df["text_input"] = eval_df["attributes.input.value"].apply(extract_text)
    eval_df["text_output"] = eval_df["attributes.output.value"].apply(extract_text)

    # 2. Split DataFrame: Forecast Agent (Reference-based) vs Others (Context-based)
    forecast_mask = eval_df["text_input"].str.contains("[forecasting_agent]", na=False)
    forecast_df = eval_df[forecast_mask].copy()
    others_df = eval_df[~forecast_mask].copy()

    all_results = []

    # --- PROCESS FORECAST AGENTS (Using Real-Time Ground Truth) ---
    if not forecast_df.empty:
        print("--- Generating Ground Truth for Forecasting Agents ---")
        forecast_df["ground_truth"] = forecast_df.apply(get_real_time_ground_truth, axis=1)
        
        correctness_evaluator = bind_evaluator(
            evaluator=CorrectnessEvaluator(llm=LLM(provider="google", model=JUDGE_MODEL)),
            input_mapping={
                "input": "text_input",
                "reference": "ground_truth",
                "output": "text_output"
            }
        )
        res_forecast = evaluate_dataframe(dataframe=forecast_df, evaluators=[correctness_evaluator])
        all_results.append(res_forecast)

    # --- PROCESS OTHER AGENTS (Using standard Faithfulness) ---
    if not others_df.empty:
        # Standard context logic from before
        others_df["context_for_judge"] = others_df["text_output"] # Defaulting to self for discovery
        
        faithfulness_evaluator = bind_evaluator(
            evaluator=FaithfulnessEvaluator(llm=LLM(provider="google", model=JUDGE_MODEL)),
            input_mapping={"input": "text_input", "context": "context_for_judge", "output": "text_output"}
        )
        res_others = evaluate_dataframe(dataframe=others_df, evaluators=[faithfulness_evaluator])
        all_results.append(res_others)

    # 3. Consolidate and Log Annotations
    final_results = pd.concat(all_results)
    annotations = []
    
    for _, row in final_results.iterrows():
        # Handle both possible score keys (correctness or faithfulness)
        score_obj = row.get("correctness_score") or row.get("faithfulness_score")
        
        if score_obj and isinstance(score_obj, dict):
            annotations.append({
                "context.span_id": row["context.span_id"],
                "annotation_name": "hallucination_check",
                "score": score_obj.get("score"),
                "label": score_obj.get("label"),
                "explanation": score_obj.get("explanation"),
                "annotator_kind": "LLM"
            })

    if annotations:
            annotations_df = pd.DataFrame(annotations)
            # Ensure we use the keyword 'dataframe'
            px_client.spans.log_span_annotations_dataframe(dataframe=annotations_df)
            print(f"✅ SUCCESS: {len(annotations_df)} spans annotated with reasoning.")
    else:
            print("❌ ERROR: No valid scores returned by judge.")

if __name__ == "__main__":
    run_hallucination_check()   