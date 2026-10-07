# Meeting Minutes Generator

An NLP project that turns a raw meeting transcript into structured minutes using the Google Gemini API.
It produces a summary, decisions, action items (owner, deadline, priority), unresolved open items, and a follow-up email.

## How it works

The project uses **prompt chaining**: three separate prompts, where the outputs of steps 1 and 2 feed step 3.

```
transcript.txt
   ├─► Step 1: Summary ──────────────────┐
   └─► Step 2: Decisions, actions, open  ┤
                                         ▼
                           Step 3: Follow-up email
                                         ▼
          outputs/minutes.json, minutes.md, follow_up_email.txt
```

## Project structure

```
meeting-minutes-ai/
├── src/
│   ├── main.py          # command-line entry point
│   ├── processor.py     # the 3-step prompt chain + Markdown report
│   ├── llm_client.py    # Gemini API wrapper (retries, fallback, JSON handling)
│   └── utils.py         # file loading, logging, JSON parsing
├── prompts/prompts.yaml # all prompts (system, summary, extraction, email)
├── config/config.yaml   # model, temperature, email tone, paths
├── data/sample_transcript.txt
├── outputs/             # sample generated output
├── tests/test_basic.py  # offline tests using a fake LLM client
├── .env.example         # API key placeholder
├── requirements.txt
└── README.md
```

## Setup

1. Clone the repository and open the folder:
```
   git clone https://github.com/ShubhikaDy/meeting-minutes-ai.git
```
2. Create and activate a virtual environment:
   - Windows (PowerShell):
```
     python -m venv venv
     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
     venv\Scripts\activate
```
   - Mac/Linux:
```
     python3 -m venv venv
     source venv/bin/activate
```
3. Install the dependencies:
```
   pip install -r requirements.txt
```
4. Get a free API key at https://aistudio.google.com/app/apikey
5. Copy `.env.example` to a new file named `.env` and paste your key:
```
   GEMINI_API_KEY=your_real_key_here
```

## Usage

Run from the project root:

```
python -m src.main                                     # uses the sample transcript
python -m src.main --input data/my_meeting.txt         # your own transcript
python -m src.main --tone friendly                     # change the email tone
python -m src.main --no-email                          # skip the email step
```

Results are printed in the terminal and saved in `outputs/`.

## Configuration (`config/config.yaml`)

| Setting | Purpose |
|---|---|
| `llm.model` | Main Gemini model |
| `llm.fallback_models` | Backup models tried if the main one is overloaded |
| `llm.temperature`, `tasks.*.temperature` | Default and per-task creativity |
| `llm.max_retries`, `retry_base_delay` | Retry behaviour with exponential backoff |
| `email.tone`, `email.sender_name` | Follow-up email style |
| `paths.*` | Prompt file, default input, output folder |

If you get a "model not found" error, change `llm.model`. Model names change often.

## Prompt design (`prompts/prompts.yaml`)

- A **system prompt** sets the role and hard rules: use only the transcript, never invent facts, write "Not specified" or "Unassigned" when unknown.
- Every task prompt defines an **exact JSON schema**.
- The extraction prompt includes a **few-shot example**.
- Unresolved issues go into a separate `open_items` list instead of being forced into decisions.
- Each step has its own temperature: low for extraction (0.1), higher for the email (0.5).

## LLM API implementation

- Retry with exponential backoff on rate limits, timeouts, and server errors
- Automatic fallback to backup models
- JSON mode with a repair attempt if the reply is not valid JSON
- In-memory caching of identical requests within a run
- Clear error messages for a missing API key or an invalid model

## Tests

```
python -m pytest -v
```

The tests use a fake LLM client, so they run offline and need no API key.

## Limitations

- Very long transcripts may exceed the model's context window (chunking is not implemented).
- Input is text only; there is no speech-to-text.
- Output quality depends on transcript quality, and LLM output can vary slightly between runs.
- Free-tier API limits apply.

## Future work

- Audio input with speech-to-text
- Chunking for long meetings
- Web interface
- Sending the email automatically
- Calendar integration

## Author

Shubhika Dubey, Manipal University Jaipur