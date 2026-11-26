import os
import json

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url   = "https://openrouter.ai/api/v1",
    api_key    = os.environ["OPENROUTER_API_KEY"]
)

MODEL = "openai/gpt-4o-mini"
CONTEXT_FILE = "json_files/01_context.json"

# ---------- Pricing (edit these if the model or rates change) ----------
# gpt-4o-mini via OpenRouter: USD per 1 million tokens
PRICE_INPUT_PER_M = 0.15
PRICE_OUTPUT_PER_M = 0.60
# Approximate exchange rate. Update it, or set USD_TO_INR in your .env
USD_TO_INR = float(os.environ.get("USD_TO_INR", 88.0))

SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are a helpful assistant. Keep replies short."
}

# Running totals for this session
total_input_tokens = 0
total_output_tokens = 0


# ---------- Helpers ----------
def save_context(messages):
    """Write the current messages list to the JSON file."""
    with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)


def load_context():
    """Load messages from the JSON file. Returns None if missing or invalid."""
    if not os.path.exists(CONTEXT_FILE):
        return None
    try:
        with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and len(data) > 0:
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


def calc_cost(input_tokens, output_tokens):
    """Return (usd, inr) cost for the given token counts."""
    usd = (input_tokens / 1_000_000) * PRICE_INPUT_PER_M \
        + (output_tokens / 1_000_000) * PRICE_OUTPUT_PER_M
    return usd, usd * USD_TO_INR


def print_usage(label, input_tokens, output_tokens):
    usd, inr = calc_cost(input_tokens, output_tokens)
    print(
        f"[{label}] input: {input_tokens} | output: {output_tokens} | "
        f"total: {input_tokens + output_tokens} tokens | "
        f"cost: ${usd:.6f} / INR {inr:.4f}"
    )


def print_final_bill():
    usd, inr = calc_cost(total_input_tokens, total_output_tokens)
    in_usd = (total_input_tokens / 1_000_000) * PRICE_INPUT_PER_M
    out_usd = (total_output_tokens / 1_000_000) * PRICE_OUTPUT_PER_M

    print("\n" + "=" * 44)
    print("              FINAL BILL (this session)")
    print("=" * 44)
    print(f"Model           : {MODEL}")
    print(f"Input tokens    : {total_input_tokens:>10}   (${in_usd:.6f})")
    print(f"Output tokens   : {total_output_tokens:>10}   (${out_usd:.6f})")
    print(f"Total tokens    : {total_input_tokens + total_output_tokens:>10}")
    print("-" * 44)
    print(f"Total cost (USD): ${usd:.6f}")
    print(f"Total cost (INR): INR {inr:.4f}  (rate: 1 USD = {USD_TO_INR})")
    print("=" * 44)


# ---------- Startup: continue or new? ----------
messages = None
saved = load_context()

if saved is not None:
    num_msgs = len(saved)
    print(f"Found a saved conversation in '{CONTEXT_FILE}' ({num_msgs} messages).")
    while True:
        choice = input("Continue it (c) or start a NEW conversation (n)? [c/n]: ").strip().lower()
        if choice in ("c", "n"):
            break
        print("Please type 'c' or 'n'.")

    if choice == "c":
        messages = saved
        print("Continuing previous conversation.")
    else:
        print("Starting a new conversation (old one will be overwritten).")
else:
    print("No saved conversation found. Starting a new one.")

if messages is None:
    messages = [SYSTEM_PROMPT.copy()]

# Save immediately so the file reflects the chosen state
save_context(messages)

print("\nType 'exit' or 'quit' to end the chat and see the final bill.")

# ---------- Chat loop ----------
try:
    while True:

        user_input = input("\nYOU: ").strip()

        if user_input.lower() in ("exit", "quit"):
            break

        if not user_input:
            continue

        # Add the current user's message
        messages.append({
            "role": "user",
            "content": user_input
        })

        # Save the exact context being sent to the LLM
        save_context(messages)

        # Call the LLM
        try:
            response = client.chat.completions.create(
                model      = MODEL,
                messages   = messages,
                max_tokens = 400
            )
        except Exception as e:
            print(f"\n[API error] {e}")
            # Remove the failed user message so the context stays clean
            messages.pop()
            save_context(messages)
            continue

        answer = response.choices[0].message.content or ""
        print("\nASSISTANT:", answer)

        # Remember the assistant's answer
        messages.append({
            "role": "assistant",
            "content": answer
        })
        save_context(messages)

        # Token usage for this response
        usage = response.usage
        in_tok = (usage.prompt_tokens or 0) if usage else 0
        out_tok = (usage.completion_tokens or 0) if usage else 0

        total_input_tokens += in_tok
        total_output_tokens += out_tok

        print()
        print_usage("This reply  ", in_tok, out_tok)
        print_usage("Session total", total_input_tokens, total_output_tokens)

except (KeyboardInterrupt, EOFError):
    print("\n\nInterrupted.")

# ---------- Quit: show final bill ----------
print_final_bill()