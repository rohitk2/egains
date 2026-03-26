# Product Recommendation Chatbot

An AI-powered chatbot that collects user preferences through conversation and recommends Apple products using Claude and LangGraph.

## Conversational Flow Chart

```mermaid
graph TD
    A((START)) --> B[orchestrator_agent]
    B -->|ask user| C[/User Input/]
    C -->|response| B
    B --> D{All preferences collected?}

    D -->|No - ask next preference| B

    D -->|Yes| F[product_query_execute]
    F -->|filter & sort| G[(products.csv)]
    G -->|top 3 results| F
    F --> H((END))

    subgraph "5 Preferences"
        P1[1. product_category]
        P2[2. budget]
        P3[3. battery_life]
        P4[4. storage]
        P5[5. ram]
    end
```
## File Overview

| File | Description |
|------|-------------|
| `server.py` | FastAPI server that manages chat sessions and exposes `/start` and `/chat` endpoints for the frontend. |
| `chatbot.py` | LangGraph-based conversational agent that uses Claude to collect user preferences and query a product database for recommendations. |
| `index.html` | Single-page chat UI that renders the conversation and displays recommended products as styled cards with Amazon search links. |
| `products.csv` | Dataset of 30+ Apple products (laptops, phones, tablets, wearables, etc.) with specs like price, battery life, RAM, and storage. |

## Brief Explanation

1. **Session start** -- The user opens the page, triggering a `GET /start` call that creates a new session and invokes the LangGraph graph with an initial greeting.
2. **Preference collection** -- The `orchestrator_agent` node sends the conversation to Claude with a system prompt instructing it to ask about preferences one at a time: product category, budget, battery life, storage, and RAM.
3. **User interaction loop** -- Each user message is sent via `POST /chat`, appended to the conversation history, and passed back through the orchestrator. Claude validates answers and asks the next question.
4. **Preference extraction** -- After all 5 preferences are collected, Claude responds with a structured JSON block. The `extract_preferences` function parses this into a validated `UserPreferences` object.
5. **Conditional routing** -- The `should_query_products` edge checks if preferences are complete. If yes, it routes to `product_query_execute`; otherwise the conversation continues.
6. **Product recommendation** -- `product_query_execute` filters `products.csv` by category, sorts by the user's stated preferences (high/low), and returns the top 3 matches.
7. **Results display** -- The server returns the product list to the frontend, which renders each product as a card with specs and an Amazon search link.

## Local Setup

1. **Clone the repo:**
   ```bash
   git clone https://github.com/rohitk2/product_recommendation_chatbot.git
   cd product_recommendation_chatbot
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create a `.env` file** in the project root with your API key:
   ```
   ANTHROPIC_API_KEY=your_key_here
   ```

4. **Start the server:**
   ```bash
   uvicorn server:app --reload
   ```

5. **Open** [http://localhost:8000](http://localhost:8000) in your browser.
