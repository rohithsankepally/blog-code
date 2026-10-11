# Banking guardrails: Point Checks and NeMo

Runnable code for the post on individual guardrails and [NVIDIA NeMo Guardrails](https://docs.nvidia.com/nemo/guardrails/index.html)

The agent in the post has three restrictions: 
1. No financial advice and no competitor comparison 
2. Authenticate before a critical action 
3. Mask card and account numbers. It can call `verify_otp`, `get_transactions`, and `transfer_money`. The dialog flow in the post calls `get_transactions_masked` only after `$authenticated` is true.


## Install and run

Tested with Python 3.11. NeMo Guardrails 0.24 requires Python 3.10 or 3.11 here, because the Presidio extra used for masking does not support 3.13, and NeMo itself does not support 3.14.

### Individual guardrails only

Any Python 3 is enough. From this directory:

```bash
python individual_guardrails.py
```

### NeMo

1. Install [Ollama](https://ollama.com/download) and start it:

   ```bash
   ollama serve
   ```

2. Pull the model the config names:

   ```bash
   ollama pull qwen2.5:3b
   ```

3. Create a virtualenv with Python 3.11 and install NeMo with the sensitive-data extra:

   ```bash
   python3.11 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python -m spacy download en_core_web_lg
   ```

   `en_core_web_lg` is the spaCy model Presidio loads for `mask sensitive data`. It is not a pip requirement.

4. Run the dry run:

   ```bash
   .venv/bin/python demo.py
   ```

`ollama serve` has to stay up while `demo.py` runs. A missing model or a stopped server fails on the first self-check call.

## File map

| File | Post |
| --- | --- |
| [individual_guardrails.py](individual_guardrails.py) | Where individual guardrails fall short |
| [demo.py](demo.py) | NeMo in action |
| [config/config.yml](config/config.yml) | Component 1 |
| [config/prompts.yml](config/prompts.yml) | Prompts for the two self-check flows |
| [config/rails.co](config/rails.co) | Component 2 |
| [config/actions.py](config/actions.py) | `get_transactions_masked` |
| [requirements.txt](requirements.txt) | `nemoguardrails[sdd]==0.24.1` |
