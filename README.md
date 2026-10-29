# Minecraft 模組下載器（Modrinth）

## 功能

依照 `mods.json` 的模組清單，從 Modrinth 下載指定 Minecraft 版本的模組。

## 安全原則

- 只新增檔案，絕不覆蓋或刪除既有檔案。
- 下載後驗證大小與雜湊值，驗證失敗不保留檔案。

## 程式結構（由上而下閱讀即可）：

1. 設定與常數
2. 資料結構（Config / ModResult）
3. 讀取設定檔
4. Modrinth API
5. 挑選版本與檔案
6. 下載與驗證
7. 已安裝清單（installed.json）
8. 處理單一模組
9. 報告
10. 主程式

## 檔案說明

### `modrinth_downloader.py`

此為自動模組下載器的主程式，不用動，從 modrinth 自動下載 mod.json 清單中指定的模組

### `mod.json` 

可自行更改成想要自動下載的模組

### `vanillatweaks_downloader.py`

此為自動下載材質包的主程式，，自動從 Vanilla Tweaks 抓取指定材質包並下載

---

# Minecraft Mod Downloader (Modrinth)

## Features

Downloads mods for a specified Minecraft version from Modrinth based on the mod list defined in `mods.json`.

## Safety Principles

- Only adds new files. Never overwrites or deletes existing files.
- Verifies file size and hash after downloading. Files that fail verification are not retained.

## Code Structure (Read from Top to Bottom)

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

## File Descriptions

### `modrinth_downloader.py`

The main program for the automatic mod downloader. No manual changes are required. It automatically downloads the mods specified in the `mods.json` list from Modrinth.

### `mods.json`

You can edit this file to specify which mods you want to download automatically.

### `vanillatweaks_downloader.py`

The main program for automatically downloading resource packs. It fetches and downloads the specified resource packs from Vanilla Tweaks.
