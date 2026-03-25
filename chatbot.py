import os
import pandas as pd
import anthropic
import json
from pydantic import BaseModel, field_validator
from typing import Literal, Optional, TypedDict
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv  

class ProductDatabase:
    def __init__(self, product_csv_path):
        self.product_db = pd.read_csv(product_csv_path)

    def get_unique_product_categories(self):
        return self.product_db["product_category"].unique().tolist()

    def get_products_schema(self):
        schema_lines = []
        for col in self.product_db.columns:
            schema_lines.append(f"{col}:{self.product_db[col].dtype}")
        return "\n".join(schema_lines)


# Initialize database first so categories are available
product_database = ProductDatabase("products.csv")
VALID_CATEGORIES = product_database.get_unique_product_categories()


class UserPreferences(BaseModel):
    product_category: str
    budget: Literal["high", "low", "No Preference"]
    battery_life: Literal["high", "low", "No Preference"]
    storage: Literal["high", "low", "No Preference"]
    ram: Literal["high", "low", "No Preference"]

    @field_validator("product_category")
    @classmethod
    def validate_product_category(cls, v):
        if v not in VALID_CATEGORIES:
            raise ValueError(f"Must be one of {VALID_CATEGORIES}")
        return v

class GraphState(TypedDict):
    conversation: list[dict]
    user_message: str
    assistant_message: str | None
    user_preferences: UserPreferences | None
    recommended_products: pd.DataFrame | None


load_dotenv()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = f"""You are a friendly product recommendation chatbot. Your job is to collect user preferences one at a time through natural conversation.

You must collect ALL of the following preferences before finishing:
1. product_category - must be one of: {VALID_CATEGORIES}
2. budget - must be one of: high, low, No Preference
3. battery_life - must be one of: high, low, No Preference
4. storage - must be one of: high, low, No Preference
5. ram - must be one of: high, low, No Preference

Rules:
- Ask about ONE preference at a time, starting with product_category.
- Be conversational and friendly.
- If the user gives an invalid answer, gently guide them to valid options.
- After collecting each preference, confirm it and move to the next one.
- Once ALL preferences are collected, respond with ONLY a JSON block in this exact format and nothing else:
{{"PREFERENCES_COMPLETE": true, "product_category": "...", "budget": "...", "battery_life": "...", "storage": "...", "ram": "..."}}

Start by greeting the user and asking what type of product they're looking for. List out the categories."""


def extract_preferences(assistant_message):
    """Check if the assistant's message contains the completed preferences JSON."""
    try:
        if "PREFERENCES_COMPLETE" in assistant_message:
            start = assistant_message.index("{")
            end = assistant_message.rindex("}") + 1
            data = json.loads(assistant_message[start:end])
            if data.get("PREFERENCES_COMPLETE"):
                del data["PREFERENCES_COMPLETE"]
                return UserPreferences(**data)
    except (ValueError, json.JSONDecodeError):
        pass
    return None


def orchestrator_agent(state: GraphState) -> dict:
    """Node 1: Single-turn — send user message to Claude, check for preferences."""
    conversation = list(state["conversation"])
    conversation.append({"role": "user", "content": state["user_message"]})

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=conversation,
    )

    assistant_msg = response.content[0].text
    conversation.append({"role": "assistant", "content": assistant_msg})
    preferences = extract_preferences(assistant_msg)

    return {
        "conversation": conversation,
        "assistant_message": assistant_msg,
        "user_preferences": preferences,
    }


def should_query_products(state: GraphState) -> str:
    """Route to product_query if preferences are complete, otherwise end."""
    if state["user_preferences"] is not None:
        return "product_query_execute"
    return END


DISPLAY_COLS = ["product_name", "price", "battery_life", "ram", "max_storage", "description"]

PREF_TO_COL = {
    "budget": "price",
    "battery_life": "battery_life",
    "storage": "max_storage",
    "ram": "ram",
}


def get_recommendations(prefs):
    """Filter and sort products based on preferences. Returns top 3 as DataFrame."""
    df = product_database.product_db.copy()
    df = df[df["product_category"] == prefs.product_category]

    sort_columns = []
    sort_ascending = []

    for pref_field, col_name in PREF_TO_COL.items():
        pref_value = getattr(prefs, pref_field)
        if pref_value == "No Preference":
            continue
        df[col_name] = pd.to_numeric(df[col_name], errors="coerce")
        sort_columns.append(col_name)
        sort_ascending.append(pref_value == "low")

    if sort_columns:
        df = df.sort_values(by=sort_columns, ascending=sort_ascending, na_position="last")

    available_cols = [c for c in DISPLAY_COLS if c in df.columns]
    return df[available_cols].head(3)


def product_query_execute(state: GraphState) -> dict:
    """Node 2: Query product database based on collected preferences."""
    df = get_recommendations(state["user_preferences"])
    print("\n--- Recommended Products ---")
    if df.empty:
        print("No products found matching your criteria.")
    else:
        print(df.to_string(index=False))
    return {"recommended_products": df}


def build_graph():
    graph_builder = StateGraph(GraphState)
    graph_builder.add_node("orchestrator_agent", orchestrator_agent)
    graph_builder.add_node("product_query_execute", product_query_execute)
    graph_builder.add_edge(START, "orchestrator_agent")
    graph_builder.add_conditional_edges("orchestrator_agent", should_query_products)
    graph_builder.add_edge("product_query_execute", END)
    return graph_builder.compile()


graph = build_graph()


if __name__ == "__main__":
    # CLI loop: invoke the graph per turn
    state = {
        "conversation": [],
        "user_message": "Hi, I need help picking a product.",
        "assistant_message": None,
        "user_preferences": None,
        "recommended_products": None,
    }

    result = graph.invoke(state)
    print(f"\nChatbot: {result['assistant_message']}")

    while result["user_preferences"] is None:
        user_input = input("\nYou: ").strip()
        if not user_input:
            continue
        result = graph.invoke({
            **result,
            "user_message": user_input,
        })
        if result["user_preferences"]:
            print("\n--- All preferences collected! ---")
            print(result["user_preferences"].model_dump_json(indent=2))
            print("\n--- Recommended Products ---")
            print(result["recommended_products"].to_string(index=False))
        else:
            print(f"\nChatbot: {result['assistant_message']}")