import os

import requests

# --- Configuration ---
# The URL of your API endpoint
API_URL = "http://0.0.0.0:8002/get_facts_by_hash"

# The FULL path to your input file containing the hashes
INPUT_HASH_FILE = (
    "/Users/vic/Desktop/hashes.txt"  # <-- Make sure this path is correct
)

# The name of the output report that will be created on your Desktop
OUTPUT_FILE_NAME = "fact_analysis_report.txt"
# ---------------------


def get_hashes_from_file(filepath):
    """Reads and cleans hashes from a text file."""
    try:
        with open(filepath) as f:
            hashes = [line.strip().strip('",') for line in f if line.strip()]
        if not hashes:
            print(f"Warning: No valid hashes found in {filepath}.")
            return []
        print(
            f"Successfully read and cleaned {len(hashes)} hash(es) from {filepath}.",
        )
        return hashes
    except FileNotFoundError:
        print(f"Error: Input file not found at '{filepath}'")
        return None


def fetch_facts_from_api(hashes):
    """Sends hashes to the API and returns the parsed JSON response."""
    if not hashes:
        return None

    payload = {"fact_hashes": hashes}
    headers = {"Content-Type": "application/json"}

    print(f"Sending request to {API_URL}...")
    try:
        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        print("Successfully received a response from the API.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while communicating with the API: {e}")
        return None


def process_and_save_facts(api_data):
    """Categorizes facts and writes a structured report to a file on the Desktop."""
    if not api_data:
        print("No data received to process.")
        return

    # Find the list of facts within the API response
    list_of_facts = []
    if isinstance(api_data, list):
        list_of_facts = api_data
    elif isinstance(api_data, dict):
        # Look for the list under a key like 'facts', 'results', 'data', etc.
        for key, value in api_data.items():
            if isinstance(value, list):
                print(f"Found list of facts under the key: '{key}'")
                list_of_facts = value
                break

    if not list_of_facts:
        print(
            "Error: Could not find a list of fact objects in the API response.",
        )
        return

    # --- Categorize the Facts ---
    print("Categorizing facts...")
    all_facts = []
    disputed_facts = []
    contradicted_facts = []
    verified_facts = []

    for fact_obj in list_of_facts:
        content = fact_obj.get("content", "Content not found.")

        # 1. Add every fact to the main list
        all_facts.append(content)

        # 2. Check the 'disputed' flag
        if fact_obj.get("disputed") is True:
            disputed_facts.append(content)

        # 3. Check the 'score' for verification or contradiction
        score = fact_obj.get("score", 0)
        if score > 0:
            verified_facts.append(content)
        elif score < 0:
            contradicted_facts.append(content)

    # --- Write the Report File ---
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    output_filepath = os.path.join(desktop_path, OUTPUT_FILE_NAME)

    print(f"Writing report to {output_filepath}...")
    try:
        with open(output_filepath, "w", encoding="utf-8") as f:
            # Helper function to write each section neatly
            def write_section(title, facts_list):
                f.write(
                    f"--- {title.upper()} (Total: {len(facts_list)}) ---\n\n",
                )
                if not facts_list:
                    f.write("None found.\n\n")
                else:
                    for i, content in enumerate(facts_list, start=1):
                        f.write(f"{i}. {content}\n\n")
                f.write("=" * 60 + "\n\n")

            # Write each section to the file using the helper
            write_section("All Facts", all_facts)
            write_section(
                "Verified or Corroborated Facts (Score > 0)",
                verified_facts,
            )
            write_section("Disputed Facts", disputed_facts)
            write_section("Contradicted Facts (Score < 0)", contradicted_facts)

        print("-" * 30)
        print("Success! The report has been saved to:")
        print(output_filepath)
        print("-" * 30)

    except OSError as e:
        print(f"Error: Could not write to the file. Reason: {e}")


def main():
    """Main function to run the script."""
    hashes = get_hashes_from_file(INPUT_HASH_FILE)
    if hashes:
        api_data = fetch_facts_from_api(hashes)
        if api_data:
            process_and_save_facts(api_data)


if __name__ == "__main__":
    main()
