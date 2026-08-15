# agy-image

Portable Agent Skill for generating verified image assets with the local
**agy (Antigravity) CLI**, with an osu! storyboard-aware workflow.

當 Codex、Claude Code 或其他 agent 在撰寫 `.osb`、`.osu`、storybrew 時發現缺少
背景、角色 cut-in、texture 或 transition plate，這個 skill 會先盤點 beatmap
既有素材；只有真的缺圖時才透過 WSL/Linux 裡的 agy 生圖、收集 artifact、驗證
格式與尺寸，最後提供可放進 storyboard 的相對路徑。

## Features

- 自動觸發 osu! storyboard 缺圖情境，也支援一般 `agy 生圖`要求。
- 生圖前強制判斷 Windows、WSL、Linux 或 macOS，選出真正有 `agy` 的執行環境，
  並把所有路徑轉成該環境可用的格式。
- 先重用現有素材，不會因縮圖、裁切或改色等簡單工作浪費生成配額。
- 使用明確像素尺寸，偵測 agy 常見的 1024x1024 fallback。
- 支援角色參考圖與多場景 subject anchor。
- 收集 agy 1.1.x 寫入 `~/.gemini/antigravity-cli/brain/` 的真實 artifact。
- 驗證 PNG、JPEG、WEBP 檔頭與實際尺寸，不會把 JPEG 假裝成 PNG。
- 透過 ffmpeg 或 WSL 的 Windows PowerShell fallback 做置中裁切、縮放及
  JPEG/PNG 轉檔。
- 預設拒絕覆寫既有檔案；`--dry-run` 不生圖也不建立目錄。
- 一份 `SKILL.md` 支援 Codex、Claude Code、Gemini CLI、GitHub Copilot/VS Code、
  OpenClaw 與其他 Agent Skills 相容工具。

## Trigger examples

會觸發：

```text
用 WSL 裡面的 agy 生一張 16:9 星空背景。
幫我寫 osu storyboard，副歌需要一張素材夾裡沒有的霓虹城市全景。
Build this storybrew scene and generate the missing character cut-in with agy.
```

不會觸發：

```text
只使用 SB/assets 裡現有圖片，不要生成新素材。
把現有的 bg.jpg 縮成 854x480。
用 Midjourney 生一張 storyboard 背景。
分析這張圖片裡有哪些物件和文字。
```

## Requirements

- Python 3.9 or newer.
- Linux，或已啟用 WSL 2 的 Windows。
- `agy` 已安裝在實際執行 wrapper 的 Linux/WSL 環境並完成登入。
- 本機 Antigravity/Gemini 帳號仍有可用生成 quota。
- ffmpeg（建議）；Windows + WSL 沒有 ffmpeg 時，可使用 Windows PowerShell
  `System.Drawing` fallback 處理 JPEG/PNG。

先在 WSL 確認：

```bash
command -v agy
agy --version
```

## Install

Clone repository：

```bash
git clone https://github.com/EricChangOwO/agy-image.git
cd agy-image
```

安裝到所有支援的 user-scope 位置：

```bash
python3 scripts/install_skill.py --agent all
```

只安裝指定 client，可重複傳入 `--agent`：

```bash
python3 scripts/install_skill.py --agent codex --agent claude
```

支援值：`codex`、`claude`、`universal`、`gemini`、`copilot`、`openclaw`、
`all`。

安裝到特定專案：

```bash
python3 scripts/install_skill.py \
  --agent all \
  --scope project \
  --project-root /path/to/project
```

先查看安裝目的地，不寫入檔案：

```bash
python3 scripts/install_skill.py --agent all --dry-run
```

| Client | User scope | Project scope |
|---|---|---|
| Codex | `~/.codex/skills/agy-image/` | `.agents/skills/agy-image/` |
| Claude Code | `~/.claude/skills/agy-image/` | `.claude/skills/agy-image/` |
| Universal Agent Skills | `~/.agents/skills/agy-image/` | `.agents/skills/agy-image/` |
| Gemini CLI | `~/.gemini/skills/agy-image/` | `.gemini/skills/agy-image/` |
| GitHub Copilot / VS Code | `~/.copilot/skills/agy-image/` | `.github/skills/agy-image/` |
| OpenClaw | `~/.openclaw/skills/agy-image/` | `.openclaw/skills/agy-image/` |

安裝後重新啟動 agent 或重新載入 skills。

## Use from an agent

安裝完成後直接描述 storyboard 工作即可，不必手動指定腳本：

```text
分析這個 beatmap 和 storybrew 專案，幫副歌做一段慢速推鏡。
如果缺少需要的背景，使用 agy 生圖並放到 SB/agy/，最後整合進 storyboard。
```

Agent 應該：

1. 先執行 runtime probe，判斷目前是 Windows、WSL 或原生 POSIX 環境。
2. 找到 beatmap root、`.osu`、`.osb` 與 storybrew source。
3. 搜尋現有 PNG/JPEG 及 storyboard 已引用的相對路徑。
4. 列出缺少的 asset manifest。
5. 一次生成一張並驗證，再決定是否繼續系列圖。
6. 只把例如 `SB/agy/chorus-city.jpg` 這類相對路徑寫入 storyboard。
7. 在 gameplay 中檢查 4:3、16:9 framing、layer、timing 與 hit-object readability。

## 必做 Step 0：偵測 runtime 與轉換路徑

不要先假設 agent 跑在哪裡，也不要先假設 distro 叫 `Ubuntu`。每次生圖前，將
skill、輸出檔和所有 reference 的**絕對路徑**交給 probe：

```powershell
$repoWindows = (Resolve-Path '.').Path
$outWindows = 'C:\path\to\beatmap\SB\agy\chorus-city.jpg'
$probe = (python scripts/runtime_probe.py `
  --path $repoWindows `
  --path $outWindows | Out-String) | ConvertFrom-Json

if ($LASTEXITCODE -ne 0 -or $probe.status -ne 'ready') {
  throw '找不到可用的 agy runtime，或路徑無法轉換'
}
if ($probe.translated_paths.error | Where-Object { $_ }) {
  throw '至少一個路徑無法轉換'
}
```

輸出 JSON 會提供：

- `generation.launcher`：wrapper 應使用的 Python runtime；
- `generation.distro`：Windows 需要進 WSL 時所選的 distro；
- `generation.agy_path`：真正的 `agy` 絕對路徑；
- `translated_paths[].generation_path`：可傳給 wrapper 的正確路徑。

如果 status 不是 `ready`、probe exit code 非零，或任何 path 有 `error`，agent 必須
停止，不可以猜路徑。Windows Python 不應解析 `/mnt/c/...`，WSL Python 也不應
解析 `C:\...`。詳細矩陣見 [runtime/path reference](references/runtime-paths.md)。

## Run the wrapper directly

### Linux / inside WSL

```bash
probe_json="$(python3 scripts/runtime_probe.py \
  --path "$(pwd)" \
  --path /home/user/agy_images/chorus-city.jpg)" || exit 1

# Read generation.agy_path and translated_paths from probe_json with the agent's
# JSON tooling, then pass those exact values:
python3 scripts/agy_image.py \
  --agy-bin /home/user/.local/bin/agy \
  --prompt "cinematic neon city at night, rain, cyan and magenta light, strong depth, no text, no logo, no watermark" \
  --width 1536 \
  --height 864 \
  --out /home/user/agy_images/chorus-city.jpg \
  --crop
```

### Windows PowerShell with agy inside WSL

```powershell
$repoWindows = (Resolve-Path '.').Path
$outWindows = 'C:\path\to\beatmap\SB\agy\chorus-city.jpg'
$probe = (python scripts/runtime_probe.py `
  --path $repoWindows --path $outWindows | Out-String) | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $probe.status -ne 'ready') { throw 'agy runtime is not ready' }

$repoWsl = $probe.translated_paths[0].generation_path
$outWsl = $probe.translated_paths[1].generation_path
wsl.exe -d $probe.generation.distro -- python3 "$repoWsl/scripts/agy_image.py" `
  --agy-bin $probe.generation.agy_path `
  --prompt 'cinematic neon city at night, rain, cyan and magenta light, strong depth, no text, no logo, no watermark' `
  --width 1536 `
  --height 864 `
  --out $outWsl `
  --crop
```

在消耗 quota 前檢查組合後的 prompt 與 command：

```bash
python3 scripts/agy_image.py \
  --prompt "test scene" \
  --width 854 --height 480 \
  --out /tmp/storyboard-test.jpg \
  --dry-run
```

## osu! asset defaults

| Asset role | Suggested final size | Format |
|---|---:|---|
| 16:9 full-screen background | 854x480 | JPEG |
| 4:3 full-screen background | 640x480 | JPEG |
| Large source for zoom or pan | 1536x864 | JPEG |
| Character cut-in | 512x768 or scene-specific | PNG after matting |
| Texture or abstract overlay | 512x512 | PNG/JPEG |

osu! storyboard 座標以 `(320,240)` 為中心。16:9 可視範圍約為 `-107..747` ×
`0..480`。agy 不保證透明背景；foreground cut-in 必須再做去背，並確認輸出的
PNG 真的含 alpha channel。

完整規則見 [osu storyboard reference](references/osu-storyboard.md)。

## Wrapper output

成功時 stdout 會輸出一個 JSON object：

```json
{
  "status": "completed",
  "out": "/home/user/agy_images/chorus-city.jpg",
  "requested": {"width": 1536, "height": 864},
  "actual": {"width": 1536, "height": 864},
  "matched": true,
  "cropped": false,
  "format": "jpeg",
  "source_artifact": "/home/user/.gemini/antigravity-cli/brain/.../image.jpg",
  "exit_code": 0
}
```

只在 `status` 為 `completed`、`matched` 為 `true`，且檔案確實存在時交付圖片。

## Security

agy print mode 無法跳出互動式權限確認，因此 wrapper 預設加入：

```text
--dangerously-skip-permissions
```

這個旗標會自動核准 agy 的本機工具呼叫。只使用已檢查的 prompt 與可信任的本機
參考圖。wrapper 同時加入 `--disable-slash-commands`，並要求 agy 只呼叫一次原生
`generate_image`，降低巢狀 skill／session 風險。

若已在 agy 設定中建立適當 allow-list，可省略廣泛授權：

```bash
AGY_REQUIRE_PERMISSIONS=1 python3 scripts/agy_image.py ...
```

## Current status

Lifecycle 目前是 **draft**。

- Agent Skills 結構、Python、JSON、installer、zero-write dry-run、artifact discovery、
  Windows→WSL runtime/path probe、WSL JPEG/PNG conversion 與隔離 storyboard
  forward-test 已通過。
- 實際 agy 測試已確認登入與單次 `generate_image` dispatch；其中一次服務端等待
  12 分鐘後 timeout，wrapper 正確回報失敗且沒有偽造輸出。
- 完整 live wrapper success 與 paired benchmark 完成後，才會升級 lifecycle 狀態。

詳情見 [readiness report](references/readiness_report.md) 與
[troubleshooting](references/troubleshooting.md)。

## Repository layout

```text
agy-image/
├── SKILL.md
├── README.md
├── agents/openai.yaml
├── scripts/
│   ├── agy_image.py
│   ├── install_skill.py
│   └── runtime_probe.py
├── references/
│   ├── agy-cli.md
│   ├── agent-compatibility.md
│   ├── osu-storyboard.md
│   ├── prompt-guide.md
│   ├── readiness_report.md
│   ├── runtime-paths.md
│   └── troubleshooting.md
├── assets/evals/
└── skill_lifecycle.yaml
```

## References

- [Agent Skills specification](https://agentskills.io/specification)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Codex skills](https://developers.openai.com/codex/skills)
- [Gemini CLI skills](https://geminicli.com/docs/cli/using-agent-skills/)
- [VS Code Agent Skills](https://code.visualstudio.com/docs/agent-customization/agent-skills)
- [osu! storyboard general rules](https://osu.ppy.sh/wiki/en/Storyboard/Scripting/General_Rules)
- [osu! storyboard objects](https://osu.ppy.sh/wiki/en/Storyboard/Scripting/Objects)
