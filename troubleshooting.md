# Troubleshooting: Resolving Quota Errors (Error 429)

If you encounter an execution error like this during a research run:

```text
Execution Error ❌
The research agent encountered an error: Error code: 429 - {'error': {'message': 'You exceeded your current quota...'}}
```

It means that your chosen API provider (e.g., OpenAI) has exhausted its credits, expired, or has no billing enabled for the provided API key.

---

## 🛠️ Solutions

### Option A: Switch to Google Gemini (Cloud-based, generous free tiers)
If you want fast cloud performance, Google Gemini is a great alternative.
1. Visit [Google AI Studio](https://aistudio.google.com/) and create a free API key.
2. In the Research Rabbit Web UI, go to the **API Keys & Settings** tab.
3. Set the **LLM Provider** to `Google Gemini`.
4. Enter your new key in the **Gemini API Key** field.
5. Click **Save Settings** and re-run your query.

### Option B: Switch to Ollama (100% Free, Private, & Local)
Running locally via Ollama ensures you never hit cloud billing quotas or run out of search agent capacity.
1. Download and install Ollama from [Ollama.com](https://ollama.com/).
2. Start the Ollama application.
3. Open your terminal and pull a lightweight model like llama3.2:
   ```bash
   ollama pull llama3.2
   ```
4. In the Research Rabbit Web UI, go to the **API Keys & Settings** tab.
5. Set the **LLM Provider** to `Ollama (Local LLM)`.
6. Set the **Ollama Model Name** to `llama3.2`.
7. Click **Save Settings** and re-run your query.
