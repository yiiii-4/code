#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
MC2 同传(interpreter)· 训练数据准备脚本

功能:
  1. 下载公开中英平行语料(走 hf-mirror 国内镜像,自动加速)
  2. 清洗 / 去重 / 按长度过滤
  3. 构造成 LLaMA-Factory 可直接用的 alpaca 格式(中文→英文、英文→中文 双向 SFT)

用法:
  # 试跑(快,先验证全链路)
  python scripts\prepare_translate_data.py --max_pairs 5000

  # 正式(2 万样本)
  python scripts\prepare_translate_data.py --max_pairs 10000

  # 不联网,先生成 6 条合成样本看看格式
  python scripts\prepare_translate_data.py --offline-test

输出(正式运行):
  ..\..\LLaMA-Factory\data\mc2_interpreter.json        完整训练集(alpaca 格式)
  ..\..\LLaMA-Factory\data\mc2_interpreter_sample.json 前 20 条预览(人看的)
"""
import argparse
import json
import os
import re
import sys
import unicodedata

# ⚠️ 训练和推理必须用同一句指令!改这里时,阶段 B 的推理端也要同步改,否则模型不听话。
INSTR_ZH2EN = "把下面的中文翻译成英语,只输出译文。"
INSTR_EN2ZH = "把下面的英语翻译成中文,只输出译文。"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))        # mc2-interpreter/scripts/
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)                      # mc2-interpreter/
REPO_ROOT = os.path.dirname(PROJECT_DIR)                       # llm_practice_project/
STAGING_DIR = os.path.join(PROJECT_DIR, "data")                # 预览/离线测试用
TRAIN_DATA_DIR = os.path.join(REPO_ROOT, "LLaMA-Factory", "data")  # 训练数据落这里,LLaMA-Factory 直接读


# ---------------- 清洗 / 过滤 / 去重 ----------------

def clean_line(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u3000", " ").replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def has_chinese(s: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", s))


def valid_pair(zh: str, en: str) -> bool:
    zh, en = clean_line(zh), clean_line(en)
    if not zh or not en:
        return False
    if not has_chinese(zh):            # 中文侧必须有汉字
        return False
    if has_chinese(en):                # 英文侧不该混中文
        return False
    if not (2 <= len(zh) <= 200):      # 过滤过短/过长(口语短句为主)
        return False
    if not (2 <= len(en) <= 400):
        return False
    if not re.search(r"[A-Za-z]", en):  # 英文侧至少要有字母
        return False
    return True


def build_rows(pairs):
    """pairs: 可迭代的 (zh, en) 句对。每句对生成双向两条 SFT 样本,并去重。"""
    seen_zh, seen_en = set(), set()
    rows = []
    for zh, en in pairs:
        zh, en = clean_line(zh), clean_line(en)
        if not valid_pair(zh, en):
            continue
        if zh in seen_zh or en in seen_en:
            continue
        seen_zh.add(zh)
        seen_en.add(en)
        rows.append({"instruction": INSTR_ZH2EN, "input": zh, "output": en})
        rows.append({"instruction": INSTR_EN2ZH, "input": en, "output": zh})
    return rows


# ---------------- 数据源(懒加载 datasets) ----------------

def _translation(ex):
    tr = ex.get("translation") or {}
    if not isinstance(tr, dict):
        return None, None
    # 各数据源的语种键名不统一:opus100/news 用 "en"/"zh",部分 tatoeba 变体用 "eng"/"zho" 等,统一兜底
    zh = tr.get("zh") or tr.get("zho") or tr.get("cmn") or tr.get("zh-CN")
    en = tr.get("en") or tr.get("eng") or tr.get("en-US")
    return zh, en


def iter_tatoeba():
    from datasets import load_dataset
    # tatoeba 支持 lang1/lang2 参数;个别版本用 "en-zh" config,都试一遍
    try:
        ds = load_dataset("tatoeba", lang1="en", lang2="zh", split="train")
    except Exception:
        ds = load_dataset("tatoeba", "en-zh", split="train")
    for ex in ds:
        yield _translation(ex)


def iter_opus100():
    from datasets import load_dataset
    ds = load_dataset("Helsinki-NLP/opus-100", "en-zh", split="train")
    for ex in ds:
        yield _translation(ex)


def iter_news():
    from datasets import load_dataset
    try:
        ds = load_dataset("news_commentary", "en-zh", split="train")
    except Exception:
        ds = load_dataset("news_commentary", "zh-en", split="train")
    for ex in ds:
        yield _translation(ex)


SOURCES = {
    "tatoeba": iter_tatoeba,   # 短句口语,最贴合面对面对话
    "opus100": iter_opus100,   # 大体量通用语料(含字幕/口语),下载较大
    "news": iter_news,         # 新闻正式语料,少量加一点即可
}


# ---------------- 主流程 ----------------

def offline_sample():
    demo = [
        ("今天天气很好,我们出去散步吧。", "The weather is nice today. Let's go for a walk."),
        ("这个多少钱?", "How much is this?"),
        ("请问洗手间在哪里?", "Excuse me, where is the restroom?"),
        ("能帮我拍张照片吗?", "Could you take a photo for me?"),
        ("我迷路了,你能帮我吗?", "I'm lost. Can you help me?"),
        ("菜很好吃,谢谢款待。", "The food is delicious. Thanks for the meal."),
    ]
    return build_rows(demo)


def write_output(rows, out_path, sample_n=20):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"[保存] {out_path}  ({len(rows)} 条样本)")

    sample_path = os.path.join(os.path.dirname(out_path), "mc2_interpreter_sample.json")
    with open(sample_path, "w", encoding="utf-8") as f:
        json.dump(rows[:sample_n], f, ensure_ascii=False, indent=2)
    print(f"[预览] {sample_path}  (前 {min(sample_n, len(rows))} 条,打开看看长啥样)")


def main():
    ap = argparse.ArgumentParser(description="MC2 翻译模型训练数据准备")
    ap.add_argument("--max_pairs", type=int, default=10000,
                    help="最多保留多少句对(每条句对生成双向 2 条样本),默认 10000")
    ap.add_argument("--sources", default="tatoeba,opus100",
                    help="逗号分隔,可选: tatoeba,opus100,news。默认 tatoeba,opus100")
    ap.add_argument("--out", default=os.path.join(TRAIN_DATA_DIR, "mc2_interpreter.json"),
                    help="训练集输出路径(默认 LLaMA-Factory/data/mc2_interpreter.json)")
    ap.add_argument("--offline-test", action="store_true",
                    help="不联网,生成 6 条合成样本,检查输出格式")
    ap.add_argument("--hf_endpoint", default=os.environ.get("HF_ENDPOINT", "https://hf-mirror.com"),
                    help="HuggingFace 镜像地址,国内默认 hf-mirror.com")
    args = ap.parse_args()

    if args.offline_test:
        rows = offline_sample()
        os.makedirs(STAGING_DIR, exist_ok=True)
        p = os.path.join(STAGING_DIR, "mc2_interpreter_sample.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        print(f"[保存] {p}  ({len(rows)} 条样本)")
        print("\n[说明] 这是合成样本,只用来确认格式;正式训练请去掉 --offline-test。")
        return

    os.environ.setdefault("HF_ENDPOINT", args.hf_endpoint)
    names = [n.strip() for n in args.sources.split(",") if n.strip()]
    unknown = [n for n in names if n not in SOURCES]
    if unknown:
        print(f"未知数据源: {unknown};可选: {list(SOURCES)}")
        sys.exit(1)

    print(f"[配置] 数据源={names}  目标句对数={args.max_pairs}  HF 镜像={args.hf_endpoint}")
    print(f"[指令1] {INSTR_ZH2EN}")
    print(f"[指令2] {INSTR_EN2ZH}")

    pairs = []
    for name in names:
        print(f"[下载] 正在获取语料: {name} …", flush=True)
        try:
            for zh, en in SOURCES[name]():
                if not zh or not en:
                    continue
                if valid_pair(zh, en):
                    pairs.append((zh, en))
                if len(pairs) >= args.max_pairs:
                    break
        except Exception as e:
            print(f"[警告] 语料 {name} 下载失败(可去掉它重试): {e}")
        if len(pairs) >= args.max_pairs:
            break

    print(f"[完成] 共读到 {len(pairs)} 条有效句对")
    rows = build_rows(pairs)
    write_output(rows, args.out, sample_n=20)
    print(f"\n[下一步] 数据集已注册到 LLaMA-Factory/data/dataset_info.json(键名 mc2_interpreter)。")
    print("接着按 docs\\训练指南.md 跑训练即可。")


if __name__ == "__main__":
    main()
