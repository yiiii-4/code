#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MC2 同传(interpreter)· 阶段 B 本地推理服务(跑在你电脑上,手机同 WiFi 访问)

流程(只听懂对方):
  手机收音(对方说英文) → Whisper 识别英文 → Qwen3-4B-translate 翻成中文
  → edge-tts(联网,自然)/ Windows 系统语音(离线降级) 读中文 → 手机播放 → MC2 耳机听到

启动:
  1. 激活 venv + 缓存落 G 盘:  在项目根目录点源 . .\\mc2-interpreter\\scripts\\set_env.ps1(或粘 README 的内联命令)
  2. 装依赖(首次):  cd mc2-interpreter; python -m pip install -r requirements_inference.txt
  3. 启动:  cd mc2-interpreter\\scripts; uvicorn server:app --host 0.0.0.0 --port 8000
"""
import asyncio
import base64
import io
import os
import re
import socket
import tempfile

import torch
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# ---------- 训练/推理指令必须一致(和 prepare_translate_data.py 里的一模一样) ----------
INSTR_EN2ZH = "把下面的英语翻译成中文,只输出译文。"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))        # mc2-interpreter/scripts/
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)                      # mc2-interpreter/
REPO_ROOT = os.path.dirname(PROJECT_DIR)                       # llm_practice_project/
MODEL_DIR = os.environ.get(
    "MC2_MODEL_DIR",
    os.path.join(REPO_ROOT, "LLaMA-Factory", "models", "qwen3-4b-translate"),
)
WHISPER_MODEL = os.environ.get("MC2_WHISPER_MODEL", "base.en")   # 英文识别,轻量
WHISPER_DEVICE = os.environ.get("MC2_WHISPER_DEVICE", "cpu")     # 建议 cpu,给翻译模型留显存
WHISPER_LANG = os.environ.get("MC2_WHISPER_LANG", "en")          # 只听懂对方 → 识别英语

if not os.path.isdir(MODEL_DIR):
    raise SystemExit(
        f"[错误] 找不到合并后的翻译模型:\n  {MODEL_DIR}\n"
        "请先按 训练指南.md 完成阶段 A(下载数据→训练→合并),再启动本服务。"
    )


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


print(f"[加载] Whisper 识别模型: {WHISPER_MODEL} ({WHISPER_DEVICE})")
from faster_whisper import WhisperModel

_whisper = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type="int8")

print(f"[加载] 翻译模型: {MODEL_DIR}")
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

_tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
_quant_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
)
_model = AutoModelForCausalLM.from_pretrained(
    MODEL_DIR,
    device_map="auto",
    quantization_config=_quant_config,
    low_cpu_mem_usage=True,
)
print(f"[就绪] 模型加载完成。手机打开: http://{lan_ip()}:8000 (连同一个 WiFi)")


def _clean(s: str) -> str:
    s = s.strip()
    # 去掉可能的思考块(保险;nothink 训练后一般不会出现)
    s = re.sub(r"/think.*?/no_think", "", s, flags=re.DOTALL)
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.DOTALL)
    s = s.replace("<|im_end|>", "").replace("<|im_start|>", "")
    return s.strip()


def translate(en_text: str) -> str:
    # 与 LLaMA-Factory qwen3_nothink 模板的 format_user 完全一致:
    #   <|im_start|>user\n{{content}}<|im_end|>\n<|im_start|>assistant\n
    # 其中 content = instruction + "\n" + input(见 converter.py:100)
    content = INSTR_EN2ZH + "\n" + en_text
    prompt = f"<|im_start|>user\n{content}<|im_end|>\n<|im_start|>assistant\n"
    inputs = _tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to(_model.device)
    with torch.no_grad():
        out = _model.generate(
            **inputs,
            max_new_tokens=128,
            do_sample=False,
            pad_token_id=_tokenizer.eos_token_id,
        )
    gen = out[0][inputs["input_ids"].shape[1]:]
    return _clean(_tokenizer.decode(gen, skip_special_tokens=True))


# ---------- TTS:edge-tts(联网,自然)/ Windows 系统语音(离线降级) ----------
def _edge_tts(text: str) -> tuple[bytes, str]:
    import edge_tts

    async def run():
        com = edge_tts.Communicate(text, voice="zh-CN-XiaoxiaoNeural")
        buf = io.BytesIO()
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        return buf.getvalue()

    return asyncio.run(run()), "audio/mpeg"


_engine = None


def _sapi_tts(text: str) -> tuple[bytes, str]:
    global _engine
    import pyttsx3

    if _engine is None:
        _engine = pyttsx3.init()
        voices = _engine.getProperty("voices")
        target = None
        for v in voices:
            langs = getattr(v, "languages", []) or []
            if any("zh" in (l or "").lower() for l in langs):
                target = v
                break
        if target is None:
            for v in voices:
                n = (v.name or "").lower()
                if any(k in n for k in ("huihui", "kangkang", "yaoyao", "chinese", "中文")):
                    target = v
                    break
        if target:
            _engine.setProperty("voice", target.id)
        _engine.setProperty("rate", 180)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    _engine.save_to_file(text, tmp.name)
    _engine.runAndWait()
    with open(tmp.name, "rb") as f:
        data = f.read()
    os.unlink(tmp.name)
    return data, "audio/wav"


def tts(text: str) -> tuple[bytes, str]:
    try:
        return _edge_tts(text)
    except Exception as e:
        print(f"[TTS] edge-tts 失败({e}),降级为 Windows 系统语音")
        return _sapi_tts(text)


# ---------- Web ----------
app = FastAPI()


@app.post("/api/translate")
def api_translate(file: UploadFile = File(...)):
    audio = file.file.read()
    try:
        segments, _info = _whisper.transcribe(io.BytesIO(audio), language=WHISPER_LANG, vad_filter=True)
        en_text = "".join(s.text for s in segments).strip()
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"识别失败:{e}"})

    if not en_text:
        return JSONResponse({"ok": False, "error": "没听清,请让对方再说一次"})

    zh_text = translate(en_text)
    tts_bytes, mime = tts(zh_text)
    return {
        "ok": True,
        "en": en_text,
        "zh": zh_text,
        "audio_b64": base64.b64encode(tts_bytes).decode("ascii"),
        "audio_mime": mime,
    }


# 静态页面(手机网页)挂到根路径
app.mount("/", StaticFiles(directory=os.path.join(PROJECT_DIR, "web"), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
