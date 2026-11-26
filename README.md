# MC2 同传(interpreter)

用自己的 **倍思 MC2 蓝牙耳机** + **本地训练的翻译模型**做"听懂对方"的同传,全程本地、永久免费,不依赖倍思官方的 AI 翻译。

- 阶段 A:下载公开中英语料 → 本地 QLoRA 微调 **Qwen3-4B-Instruct-2507** → 合并出翻译模型
- 阶段 B:本地 FastAPI 服务(Whisper 识别 + 模型翻译 + 双模式 TTS)→ 手机网页 → 译文播进 MC2 耳朵

## 目录结构

```
mc2-interpreter/
├── scripts/
│   ├── set_env.ps1                  缓存重定向:模型/数据/pip/torch 全落 G 盘(每次开窗口先跑)
│   ├── prepare_translate_data.py   阶段 A:下载/清洗/生成训练数据(alpaca 格式)
│   └── server.py                   阶段 B:FastAPI 推理服务(识别→翻译→TTS)
├── configs/
│   ├── train_qwen3_4b.yaml         训练配置(QLoRA,8GB 显存可跑)
│   ├── export_merge.yaml           合并 LoRA 配置
│   └── chat_test.yaml              命令行试效果配置
├── web/
│   └── index.html                  手机网页(收音→上传→播放译文)
├── docs/
│   ├── 训练指南.md                  阶段 A 完整步骤
│   └── 阶段B使用说明.md             阶段 B 完整步骤(含 MC2 连接)
├── data/                           预览/离线测试样本(生成物)
└── requirements_inference.txt      阶段 B 依赖(fastapi/whisper/tts)
```

## 依赖两个外置东西(不搬进本项目)

- `..\venv_llm\` — Python 虚拟环境(已装 LLaMA-Factory、torch、transformers 等)。Windows venv 绝对路径写死,**不能移动**。
- `..\LLaMA-Factory\` — 训练框架(0.9.6.dev0),训练/合并/试效果都在它里面跑;训练数据写到它的 `data\` 目录,合并模型输出到它的 `models\qwen3-4b-translate\`。

## 两步上手

**第一步:训练(阶段 A)** —— 见 `docs\训练指南.md`

```powershell
cd "G:\Gesture Analysis\llm_practice_project"
. .\mc2-interpreter\scripts\set_env.ps1   # 激活 venv + 缓存全落 G 盘(见下方「缓存去向」)

cd mc2-interpreter
python scripts\prepare_translate_data.py --max_pairs 10000   # 生成训练数据(2 万条样本)
cd ..\LLaMA-Factory
llamafactory-cli train ..\mc2-interpreter\configs\train_qwen3_4b.yaml
llamafactory-cli export ..\mc2-interpreter\configs\export_merge.yaml
```

**第二步:本地推理(阶段 B)** —— 见 `docs\阶段B使用说明.md`

```powershell
cd "G:\Gesture Analysis\llm_practice_project"
. .\mc2-interpreter\scripts\set_env.ps1   # 激活 venv + 缓存落 G 盘
cd mc2-interpreter\scripts
python -m pip install -r ..\requirements_inference.txt   # 首次(用 python -m pip 确保装进 venv)
uvicorn server:app --host 0.0.0.0 --port 8000
```

手机连同一 WiFi → 浏览器打开 `http://<电脑IP>:8000` → 配好 MC2 → 开聊。

## 缓存去向(全部在 G 盘,C 盘不落缓存)

运行 `set_env.ps1` 后,所有模型与缓存都重定向到项目根目录下,不再写 C 盘用户目录:

| 内容 | 位置(都在 `G:\Gesture Analysis\llm_practice_project\`) |
|---|---|
| HuggingFace 模型 + 数据集 | `.hf_cache\`(Qwen3-4B 基座模型 ~8GB、tatoeba/opus100 数据集) |
| pip 下载缓存 | `.pipcache\` |
| PyTorch 缓存 / 编译缓存 | `.torch_cache\` / `torchinductor_yiiii\` |
| 临时文件 | `.tmp\` |

> 作用范围是**当前 PowerShell 窗口**,关掉失效;下次开窗口记得再跑一次 `set_env.ps1`。想永久生效可在"系统环境变量"里手动设置同名变量(路径同上),或每次训练前跑脚本。

## 关键约定(改了会出问题)

- 训练/推理的指令句必须一致:`INSTR_EN2ZH = "把下面的英语翻译成中文,只输出译文。"`(见 `scripts\server.py:29` 和 `scripts\prepare_translate_data.py`)。
- 训练用 `template: qwen3_nothink`(Qwen3 是思考型模型,`qwen3` 模板会先思考再答,实时翻译又慢又啰嗦)。
- 数据集在 LLaMA-Factory 里注册为 `mc2_interpreter`(见 `..\LLaMA-Factory\data\dataset_info.json`)。
