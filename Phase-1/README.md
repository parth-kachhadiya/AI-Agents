# **Agents Fundamental**

### 💡 The big idea : `API is stateless`
- **When you chat with LLM in app, it feels like remembers you. The raw API doesn't remember anything. Every call is a fresh start, and you send the entire conversation again each time. Once this clicks, the rest follows : `tokens`, `context-window`, `cost`, `memory` and `context-engineering`.**

### **1️⃣ `Messages and roles`**

> **A request is basically a list of messsages. Each has a role and content:**

- **`User`      : What the human (or your code) says.**
- **`Assistant` : What the model said earlier (you put it back into the list yourself).**
- **`System`    : Instructions about how the model should behave. In Anthropic's API this is a separate `system` parameter, not partof the messages list. OpenAI-style APIs put it inside the list instead. Know both, since you'll meet both.**

> Roles alternate **User → Assistant → User**. The model only `sees` what you put in that list.

### **2️⃣ Tokens**

> **The model doesn't read characters or words, it reads tokens, which are chunks of text. Roughtly 1 token ~3/4 of an English word but code, numbers and non-English text often use more. Two things are measured in tokens:**

1. `Input tokens`  : Everything you send (system + all messages).
2. `Output tokens` : What the model writes back.

### **3️⃣ Contest Window**

> **This is the maximum number of tokens te model can handle in one call, input and output together. Fill it up and the call fails or you have to cut htings. Even before it's full, very long contexts can make the model worse (you'll meet this later as context rot in Topic-8).**


- **Context window can contains:**
    1. *System/Developer instructions*
    2. *Previous conversation messages.*
    3. *Current user messages.*
    4. *Tool results.*
    5. *Other information supplied to the model.*
    6. *Generated output, within the applicable limits.*

- **Possbile solutions when context gets full:**
    1. *Remove irrelevant old messages.*
    2. *Summarize previous conversations.*
    3. *Retrieve only relevant information.*
    4. *Keep important information separately in memory.*


### **4️⃣ Stop reasons**

> **Every response tells you why the model stopped. This matters a lot for agents:**

- `end_turn`      : The model finished naturally.
- `max_tokens`    : You cut it off with your limit, so the answer may be incomplete.
- `stop_sequence` : It hit a custom stop string you set.
- `tool_use`      : The model wants to call a tool (this is the heart of Topic-2 and Topic-3).
- `content_filter`: Blocked by safety filters

> Your code should branch on `stop_reason`. Ignoring it is a classic beginner bug.

### **5️⃣ Cost**

> **Providers charge per token, with a different price for input and output (output is usually more expensive).**

```python
    cost = (input_tokens / 1_000_000 × input_price_per_M)
     + (output_tokens / 1_000_000 × output_price_per_M)
```

- **Prices are usually quoted per million tokens. Check the official pricing page for the model you use, because prices change. In an agent loop you resend a growing history every step, so cost grows faster than you'd expect. Keep that in mind for later phases.**
