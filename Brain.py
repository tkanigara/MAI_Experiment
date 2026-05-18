import os

from dotenv import load_dotenv
from huggingface_hub import InferenceClient


load_dotenv()


# Untuk prototype cepat, API key boleh ditempel di sini dulu.
# Nanti kalau sudah production, pindahkan lagi ke .env / secret manager.
HARDCODED_HF_API_KEY = "PASTE_HUGGINGFACE_API_KEY_HERE"


def _get_api_key():
    for name in ("HF_API_KEY", "HUGGINGFACE_API_KEY", "HF_TOKEN"):
        value = os.getenv(name)
        if value:
            return value
    if HARDCODED_HF_API_KEY != "PASTE_HUGGINGFACE_API_KEY_HERE":
        return HARDCODED_HF_API_KEY
    raise RuntimeError(
        "Missing Hugging Face API key. Isi HF_API_KEY di .env atau paste ke "
        "HARDCODED_HF_API_KEY di Brain.py."
    )


# LLM hanya bertugas memahami bahasa manusia dan menyusun jawaban.
# Eksekusi tool tetap dilakukan oleh orchestrator di Main.py.
HF_API_KEY = _get_api_key()
HF_MODEL = os.getenv("HF_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct")
HF_PROVIDER = os.getenv("HF_PROVIDER", "auto")
HF_MAX_TOKENS = int(os.getenv("HF_MAX_TOKENS", "700"))

client = InferenceClient(
    api_key=HF_API_KEY,
    model=HF_MODEL,
    provider=HF_PROVIDER,
)


def _format_hf_error(error):
    response = getattr(error, "response", None)
    details = []

    if response is not None:
        details.append(f"status_code={getattr(response, 'status_code', 'unknown')}")
        try:
            details.append(f"response={response.text}")
        except Exception:
            pass

    if not details:
        details.append(str(error))

    return "\n".join(details)


def call_llm(messages):
    try:
        response = client.chat.completions.create(
            messages=messages,
            max_tokens=HF_MAX_TOKENS,
        )
        return response.choices[0].message.content
    except Exception as error:
        raise RuntimeError(
            "Hugging Face LLM request failed.\n"
            f"Model: {HF_MODEL}\n"
            f"Provider: {HF_PROVIDER}\n"
            f"{_format_hf_error(error)}\n\n"
            "Cek HF_API_KEY/HF_TOKEN, akses ke model, nama model, dan provider."
        ) from error
