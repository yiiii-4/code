# set_env.ps1 —— 一步完成:激活 venv + 把所有模型/缓存重定向到 G 盘(C 盘不落缓存)。
# 用法:每次训练 / 推理前,先 cd 到项目根,再跑(注意前面的点号 . 不能少):
#   cd "G:\Gesture Analysis\llm_practice_project"
#   . .\mc2-interpreter\scripts\set_env.ps1
# 作用范围:当前 PowerShell 会话(关掉窗口失效,下次开窗口再跑一次)。
# 说明:本项目 venv 没有自带的 Activate.ps1,所以这里直接加 PATH 等价激活。

$Root = "G:\Gesture Analysis\llm_practice_project"

# ---- 1. 激活 venv(把 venv 的 Scripts 目录加到 PATH 最前面)----
$env:VIRTUAL_ENV = "$Root\venv_llm"
$env:PATH = "$env:VIRTUAL_ENV\Scripts;" + $env:PATH

# ---- 2. 缓存重定向:目标目录不存在就建 ----
$dirs = @(
    "$Root\.hf_cache",
    "$Root\.hf_cache\hub",
    "$Root\.hf_cache\datasets",
    "$Root\.pipcache",
    "$Root\.torch_cache",
    "$Root\.tmp"
)
foreach ($d in $dirs) { New-Item -ItemType Directory -Force -Path $d | Out-Null }

# ---- 3. HuggingFace(最大头:Qwen3-4B 基座模型 ~8GB + 数据集,都落这里)----
$env:HF_HOME               = "$Root\.hf_cache"
$env:HF_HUB_CACHE          = "$Root\.hf_cache\hub"
$env:HUGGINGFACE_HUB_CACHE = "$Root\.hf_cache\hub"
$env:TRANSFORMERS_CACHE    = "$Root\.hf_cache\hub"
$env:HF_DATASETS_CACHE     = "$Root\.hf_cache\datasets"
$env:HF_ENDPOINT           = "https://hf-mirror.com"   # 国内镜像,模型和数据都走这

# ---- 4. pip 缓存(覆盖 pip.ini 里旧的 F 盘路径)----
$env:PIP_CACHE_DIR = "$Root\.pipcache"

# ---- 5. PyTorch 缓存 + 编译缓存 ----
$env:TORCH_HOME              = "$Root\.torch_cache"
$env:TORCHINDUCTOR_CACHE_DIR = "$Root\torchinductor_yiiii"

# ---- 6. 临时目录(pip 构建、torch 编译临时文件,避免写 C 盘 %TEMP%)----
$env:TMP    = "$Root\.tmp"
$env:TEMP   = "$Root\.tmp"
$env:TMPDIR = "$Root\.tmp"

Write-Host ""
Write-Host "========== venv 已激活 + 缓存全部重定向到 G 盘 ==========" -ForegroundColor Green
Write-Host ("venv Python : " + $env:VIRTUAL_ENV + "\Scripts\python.exe")
Write-Host ("HF 模型/数据 : " + $env:HF_HOME)
Write-Host ("pip 缓存     : " + $env:PIP_CACHE_DIR)
Write-Host ("torch 缓存   : " + $env:TORCH_HOME)
Write-Host ("临时目录     : " + $env:TMP)
Write-Host "=========================================================="
Write-Host ""
