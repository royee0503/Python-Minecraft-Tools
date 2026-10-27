# Minecraft 模組下載器（Modrinth）

---

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

---

## 檔案說明

### `modrinth_downloader.py`

此為自動模組下載器的主程式，不用動，從 modrinth 自動下載 mod.json 清單中指定的模組

### `mod.json` 

可自行更改成想要自動下載的模組

---
