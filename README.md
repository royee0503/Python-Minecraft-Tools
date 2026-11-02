# Minecraft Tools

---

### 功能

依照 `mods.json` 中定義的模組清單，從 Modrinth 下載指定 Minecraft 版本的模組。

### 安全原則

- 只會新增檔案，絕不覆蓋或刪除現有檔案。
- 下載後會驗證檔案大小與雜湊值（hash），驗證失敗的檔案不會保留。

### 程式結構（由上往下閱讀）

1. 設定與常數
2. 資料結構（`Config` / `ModResult`）
3. 載入設定檔
4. Modrinth API
5. 選擇版本與檔案
6. 下載與驗證
7. 已安裝模組清單（`installed.json`）
8. 處理單一模組
9. 報告
10. 主程式

### 檔案說明

#### `modrinth_downloader.py` - Minecraft 模組下載器（Modrinth）

自動模組下載器的主程式，不需要手動修改。它會自動從 Modrinth 下載 `mods.json` 清單中指定的模組。

#### `mods.json`

你可以編輯這個檔案，指定要自動下載哪些模組。

#### `vanillatweaks_downloader.py` - Minecraft 材質包下載器（Vanilla Tweaks）

自動下載材質包的主程式，會從 Vanilla Tweaks 取得並下載指定的材質包。

---

### Features

Downloads mods for a specified Minecraft version from Modrinth based on the mod list defined in `mods.json`.

### Safety Principles

- Only adds new files. Never overwrites or deletes existing files.
- Verifies file size and hash after downloading. Files that fail verification are not retained.

### Code Structure (Read from Top to Bottom)

1. Configuration and Constants
2. Data Structures (`Config` / `ModResult`)
3. Load Configuration File
4. Modrinth API
5. Select Versions and Files
6. Download and Verification
7. Installed Mods List (`installed.json`)
8. Process Individual Mods
9. Report
10. Main Program

### File Descriptions

#### `modrinth_downloader.py` - The Minecraft Mod Downloader (Modrinth)

The main program for the automatic mod downloader. No manual changes are required. It automatically downloads the mods specified in the `mods.json` list from Modrinth.

#### `mods.json`

You can edit this file to specify which mods you want to download automatically.

#### `vanillatweaks_downloader.py` - The Minecraft Texture Pack Downloader (Vanilla Tweaks)

The main program for automatically downloading resource packs. It fetches and downloads the specified resource packs from Vanilla Tweaks.
