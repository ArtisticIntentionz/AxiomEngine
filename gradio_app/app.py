import gradio as gr
import requests
import os

# --- Configurations ---
# Uses the Hugging Face Secret if available, otherwise falls back to your AWS IP.
AXIOM_NODE_API_URL = os.environ.get("AXIOM_NODE_API_URL", "http://3.16.36.97:8000")

# --- Core Logic ---
def search_the_ledger(question_text):
    if not question_text or not question_text.strip():
        return "Please ask a question first."

    # --- FIX #1: Use the correct '/chat' endpoint ---
    search_endpoint = f"{AXIOM_NODE_API_URL}/chat"

    try:
        # Send the request to your running Axiom node
        response = requests.post(search_endpoint, json={"query": question_text}, timeout=20)
        response.raise_for_status() # Raise an exception for bad status codes

        data = response.json()
        results = data.get("results", [])

        if not results:
            return "No relevant facts found in the ledger."

        # --- FIX #2: Format the list of dictionaries correctly ---
        # We will create a formatted string from each result dictionary.
        formatted_output = []
        for result in results:
            content = result.get('content', 'No content found.')
            similarity = result.get('similarity', 0) * 100
            
            # Create a nice title based on the confidence score
            if similarity > 85:
                title = f"High Confidence Answer ({similarity:.1f}% Match)"
            elif similarity > 65:
                title = f"Related Fact Found ({similarity:.1f}% Match)"
            else:
                title = f"Possible Hint Found ({similarity:.1f}% Match)"
            
            formatted_output.append(f"{title}:\n\"{content}\"")
        
        return "\n\n---\n\n".join(formatted_output)

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Axiom node: {e}")
        return (
            "Error: Could not connect to a live Axiom node. "
            "The node might be offline or the URL might be incorrect."
        )
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return "An unexpected server-side error occurred."


# --- User Interface ---
iface = gr.Interface(
    fn=search_the_ledger,
    inputs=gr.Textbox(lines=2, placeholder="Ask a question...", label="Question"),
    outputs=gr.Textbox(label="Results from the Ledger"),
    title="Axiom: A Decentralized Network for Verifiable Truth",
    description="Ask a question to search the decentralized ledger of verified facts. The client will attempt to connect to a live node to retrieve the answer.",
    allow_flagging="never",
    examples=[["any news about trump?"], ["what happened in Nigeria?"]]
)

# --- Launch the App ---
iface.launch()