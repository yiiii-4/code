# MC2 同传(interpreter)· 阶段 B 使用说明(本地推理 + MC2 耳机)

前置:已完成阶段 A(训练 + 合并),生成了 `LLaMA-Factory\models\qwen3-4b-translate\`。

## 一、装依赖(只装一次)

```powershell
cd "G:\Gesture Analysis\llm_practice_project"
. .\mc2-interpreter\scripts\set_env.ps1   # 激活 venv + 缓存落 G 盘(Whisper 模型 ~74MB 也走 .hf_cache)
python -m pip install -r mc2-interpreter\requirements_inference.txt
```

## 二、启动服务

```powershell
cd mc2-interpreter\scripts
uvicorn server:app --host 0.0.0.0 --port 8000
```

- 首次启动会加载模型(约 20–40 秒),看到 `[就绪] 模型加载完成。手机打开: http://192.168.x.x:8000` 即可。
- 查电脑局域网 IP:命令行 `ipconfig`,看「无线局域网适配器 WLAN」的 **IPv4 地址**(形如 192.168.1.5)。

## 三、手机 + MC2 耳机

1. 手机连到**和电脑同一个 WiFi**。
2. 手机蓝牙配对 **倍思 MC2**:长按耳机进配对模式 → 手机「设置→蓝牙」选 MC2 连接。连好后手机所有声音从 MC2 出来。
3. 手机浏览器打开 `http://<电脑IP>:8000`(把 `<电脑IP>` 换成上面查到的 IP)。
4. 页面两个按钮:
   - **🎤 按住说话**:按住录音、松开翻译(普通 http 下会自动隐藏,用下面那个)。
   - **📁 录音上传**:点一下调起系统录音 → 录完自动上传翻译(**普通 http 也能用,最稳**)。
5. 对方说英语时把手机麦克风对着他 → 录一句 → 结束 → 几秒后你从 MC2 耳机听到中文翻译。

## 四、说明与排错

- **翻译慢 / 显存不足**:默认 Whisper 跑 CPU(`MC2_WHISPER_DEVICE=cpu`)、翻译模型 4-bit 跑 GPU,8GB 够用。想更快可设 `$env:MC2_WHISPER_MODEL="small.en"`(更准但更慢)。
- **没声音**:确认手机媒体音量开、且蓝牙输出走的是 MC2(不是手机外放)。edge-tts 需联网;断网会自动降级 Windows 系统语音(较机械)。
- **手机打不开页面(连不上)**:八成是 Windows 防火墙拦了。首次 `uvicorn` 启动时会弹「Windows 安全中心警报」,勾选**专用网络**并点「允许访问」;若已点拒绝,到「设置→网络和 Internet→高级网络设置→Windows 防火墙→允许应用通过防火墙」里把 Python 勾上专用网络。
- **识别不准**:让对方说慢点、离手机近点;`base.en` 够日常,想更准换 `small.en`。
- **换翻译方向(中→英)**:改 `scripts\server.py` 里的 `INSTR_EN2ZH` 为 `INSTR_ZH2EN`、`WHISPER_LANG` 默认值 `"en"` 改 `"zh"`(数据本来就是双向的,模型两边都会)。

## 五、以后每天怎么用

```powershell
cd "G:\Gesture Analysis\llm_practice_project"
. .\mc2-interpreter\scripts\set_env.ps1   # 激活 venv + 缓存落 G 盘
cd mc2-interpreter\scripts
uvicorn server:app --host 0.0.0.0 --port 8000
```

手机打开 `http://<电脑IP>:8000` → 连 MC2 → 开聊。全程本地,不花一分钱。
