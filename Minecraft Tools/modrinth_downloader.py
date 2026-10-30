from __future__ import annotations
import hashlib
import json
import re
import shutil
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote
import requests


# =========================================================
# 1. 設定與常數
# =========================================================

API_BASE = "https://api.modrinth.com/v2"

# Modrinth 要求 User-Agent 能辨識「是哪個程式、怎麼聯絡作者」。
# 偽裝成瀏覽器反而可能被限流或封鎖。
# 若要公開程式，請在括號內填上自己的聯絡方式（例如 GitHub 網址）。
USER_AGENT = "mc-mod-manager/2.0 (personal use)"

TIMEOUT = (10, 60)          # (連線逾時, 讀取逾時) 秒
CHUNK_SIZE = 1024 * 256     # 每次讀寫 256 KB
REQUEST_DELAY = 0.15        # 每個模組之間的間隔秒數，避免請求過密
MAX_RATE_LIMIT_WAIT = 60    # 遇到 429 時，最多願意等幾秒再重試

# 執行 .py 時用程式所在資料夾；Jupyter 沒有 __file__，改用目前資料夾。
try:
    BASE_DIR = Path(__file__).resolve().parent
except NameError:
    BASE_DIR = Path.cwd()

CONFIG_PATH = BASE_DIR / "mods.json"

REPORT_FILENAME = "download_report.json"
INSTALLED_FILENAME = "installed.json"

# 結果分類
RESULT_SUCCESS = "success"          # 下載成功
RESULT_SKIPPED = "skipped"          # 檔案已存在，略過（不是錯誤）
RESULT_NOT_UPDATED = "not_updated"  # 模組尚未更新（不是錯誤）
RESULT_ERROR = "error"              # 發生錯誤

# 所有 HTTP 請求共用同一個 Session：重複使用連線，User-Agent 只需設定一次。
SESSION = requests.Session()
SESSION.headers["User-Agent"] = USER_AGENT


class ModrinthError(Exception):
    """預期內的錯誤（設定、API、下載），主程式會統一捕捉並顯示。"""


# =========================================================
# 2. 資料結構
# =========================================================

@dataclass
class Config:
    """mods.json 驗證後的內容。"""
    mods: list[dict[str, Any]]
    loaders: list[str]
    version_types: list[str]
    repository_dir: Path


@dataclass
class ModResult:
    """單一模組的處理結果，會寫進報告。"""
    project: str
    result: str
    status: str
    version: str = ""
    filename: str = ""
    warnings: list[str] = field(default_factory=list)


# =========================================================
# 3. 讀取設定檔
# =========================================================

def _require_str_list(value: Any, key: str) -> list[str]:
    """確認設定值是「非空字串陣列」，否則丟出錯誤。"""
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) for item in value)
    ):
        raise ModrinthError(f"mods.json 的 {key} 必須是非空字串陣列。")
    return value


def load_config() -> Config:
    """讀取並驗證 mods.json。所有設定檢查都集中在這裡。"""
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ModrinthError(f"找不到設定檔：{CONFIG_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise ModrinthError(f"mods.json 格式錯誤：{exc}") from exc

    if not isinstance(raw, dict):
        raise ModrinthError("mods.json 最外層必須是 JSON object。")

    mods = raw.get("mods")
    if not isinstance(mods, list) or not mods:
        raise ModrinthError("請在 mods.json 的 mods 陣列中至少設定一個模組。")

    return Config(
        mods=mods,
        loaders=_require_str_list(raw.get("loaders", ["fabric"]), "loaders"),
        version_types=_require_str_list(
            raw.get("version_types", ["release"]), "version_types"
        ),
        repository_dir=Path(
            raw.get("repository_dir", "~/Documents/Minecraft Mod Repository")
        ).expanduser(),
    )


def safe_version_folder(version: str) -> str:
    """
    確認版本名稱可以安全當作資料夾名稱。
    例如 1.21.1 合法；../test 不合法（會跑到別的資料夾）。
    """
    if not re.fullmatch(r"[A-Za-z0-9._+-]+", version) or version in {".", ".."}:
        raise ModrinthError("版本名稱只能包含英數字、點、底線、加號或減號。")
    return version


# =========================================================
# 4. Modrinth API
# =========================================================

def api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    """
    對 Modrinth API 發送 GET 請求，回傳解析後的 JSON。
    遇到 429（請求過多）時，依照 API 指示的秒數等待後重試一次。
    """
    url = f"{API_BASE}{path}"

    for attempt in range(2):
        try:
            response = SESSION.get(url, params=params, timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise ModrinthError(f"連線 Modrinth API 失敗：{exc}") from exc

        if response.status_code == 429 and attempt == 0:
            # X-Ratelimit-Reset：距離限制解除還有幾秒
            wait = int(response.headers.get("X-Ratelimit-Reset", "10"))
            if wait <= MAX_RATE_LIMIT_WAIT:
                print(f"  - Modrinth 請求過多，等待 {wait} 秒後重試…")
                time.sleep(wait + 1)
                continue

        if response.status_code == 404:
            raise ModrinthError(f"Modrinth 找不到專案或版本：{url}")
        if response.status_code == 429:
            raise ModrinthError("Modrinth API 回覆 429（請求過多），請稍後再試。")

        try:
            response.raise_for_status()
            return response.json()
        except ValueError as exc:
            # 要放在 RequestException 前面：
            # 新版 requests 的 JSON 錯誤同時屬於兩種例外。
            raise ModrinthError("Modrinth API 回傳的內容不是有效 JSON。") from exc
        except requests.RequestException as exc:
            raise ModrinthError(f"Modrinth API 回應錯誤：{exc}") from exc

    raise ModrinthError("Modrinth API 重試後仍失敗。")


def get_project_versions(
    project: str,
    game_version: str | None,
    loaders: list[str],
) -> list[dict[str, Any]]:
    """
    查詢模組在指定 Minecraft 版本與 Loader 下的所有版本，新版在前。
    game_version 為 None 時不限制遊戲版本（用來查模組最新支援到哪一版）。
    """
    params: dict[str, Any] = {
        "loaders": json.dumps(loaders),
        "include_changelog": "false",
    }
    if game_version is not None:
        params["game_versions"] = json.dumps([game_version])

    data = api_get(f"/project/{quote(project, safe='')}/version", params)

    if not isinstance(data, list):
        raise ModrinthError(f"專案 {project} 的版本資料格式不符合預期。")

    # API 通常已經新版在前，但文件沒有保證，自己排序比較保險。
    return sorted(
        data,
        key=lambda v: v.get("date_published", ""),
        reverse=True,
    )


def get_project_names(project_ids: list[str]) -> dict[str, str]:
    """
    一次查詢多個專案的名稱，回傳 {專案 ID: 名稱}。
    查詢失敗時回傳空字典，呼叫端會改顯示 ID。
    """
    if not project_ids:
        return {}
    try:
        data = api_get("/projects", {"ids": json.dumps(project_ids)})
    except ModrinthError:
        return {}
    return {
        item["id"]: item.get("title", item["id"])
        for item in data
        if isinstance(item, dict) and "id" in item
    }


# =========================================================
# 5. 挑選版本與檔案
# =========================================================

def _valid_files(version: dict[str, Any]) -> list[dict[str, Any]]:
    """回傳版本中具有下載網址與檔名的檔案。"""
    return [
        f for f in (version.get("files") or [])
        if isinstance(f, dict) and f.get("url") and f.get("filename")
    ]


def choose_version(
    versions: list[dict[str, Any]],
    allowed_types: list[str],
) -> dict[str, Any] | None:
    """從版本清單中挑出第一個（最新）允許類型、仍上架、且有檔案的版本。"""
    for version in versions:
        if (
            version.get("version_type") in allowed_types
            and version.get("status", "listed") == "listed"
            and _valid_files(version)
        ):
            return version
    return None


def choose_file(version: dict[str, Any]) -> dict[str, Any] | None:
    """優先選擇標記為 primary 的檔案，否則用第一個有效檔案。"""
    files = _valid_files(version)
    if not files:
        return None
    return next((f for f in files if f.get("primary")), files[0])


def explain_not_updated(
    project: str,
    game_version: str,
    config: Config,
    versions: list[dict[str, Any]],
) -> str:
    """找不到可下載版本時，判斷原因並回傳說明文字（不是錯誤）。"""
    loader_text = ", ".join(config.loaders)

    # 情況 1：目標版本有檔案，只是都是 beta/alpha。
    if versions:
        found = sorted({str(v.get("version_type", "未知")) for v in versions})
        return (
            f"模組尚未推出 Minecraft {game_version} 的正式版"
            f"（目前只有：{', '.join(found)}；"
            f"設定只接受：{', '.join(config.version_types)}）"
        )

    # 不限遊戲版本再查一次，看模組最新支援到哪一版。
    all_versions = get_project_versions(project, None, config.loaders)

    # 情況 2：完全沒有這個 Loader 的版本。
    if not all_versions:
        return f"此模組沒有 {loader_text} 版本"

    # 情況 3：有這個 Loader，但還沒更新到目標版本。
    latest = choose_version(all_versions, config.version_types) or all_versions[0]
    latest_games = latest.get("game_versions") or []
    if not latest_games:
        return f"模組尚未更新至 Minecraft {game_version}"

    return (
        f"模組尚未更新至 Minecraft {game_version}"
        f"（{loader_text} 最新版本 {latest.get('version_number', '未知')} "
        f"支援：{', '.join(latest_games[-3:])}）"
    )


# =========================================================
# 6. 下載與驗證
# =========================================================

def download_file(file_info: dict[str, Any], destination: Path) -> None:
    """
    下載檔案到 destination，並驗證大小與雜湊值。

    流程：
        1. 下載到 .part 暫存檔，同時計算雜湊（不必再重讀檔案）。
        2. 驗證大小與雜湊。
        3. 驗證通過才以 "xb" 模式建立正式檔（檔案已存在就失敗，絕不覆蓋）。
    無論成功或失敗，最後都會刪除暫存檔。
    """
    filename = destination.name
    temp_path = destination.with_name(f".{filename}.part")

    # 優先用 SHA-512，沒有才用 SHA-1；兩者都沒有就不下載。
    hashes = file_info.get("hashes") or {}
    if hashes.get("sha512"):
        algorithm, expected_hash = "sha512", hashes["sha512"]
    elif hashes.get("sha1"):
        algorithm, expected_hash = "sha1", hashes["sha1"]
    else:
        raise ModrinthError(f"{filename} 沒有可用的 SHA-512/SHA-1，為安全起見不下載。")

    digest = hashlib.new(algorithm)
    total = 0
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        with SESSION.get(file_info["url"], stream=True, timeout=TIMEOUT) as response:
            response.raise_for_status()
            with temp_path.open("wb") as output:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    output.write(chunk)
                    digest.update(chunk)
                    total += len(chunk)

        expected_size = file_info.get("size")
        if expected_size is not None and total != int(expected_size):
            raise ModrinthError(
                f"{filename} 大小不符：下載 {total} bytes，API 預期 {expected_size} bytes。"
            )

        if digest.hexdigest().lower() != expected_hash.lower():
            raise ModrinthError(f"{filename} 的 {algorithm.upper()} 驗證失敗。")

        with temp_path.open("rb") as source, destination.open("xb") as target:
            shutil.copyfileobj(source, target, CHUNK_SIZE)

    except FileExistsError as exc:
        raise ModrinthError(f"檔案已存在，未覆蓋：{filename}") from exc
    except requests.RequestException as exc:
        raise ModrinthError(f"下載 {filename} 失敗：{exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)


# =========================================================
# 7. 已安裝清單（installed.json）
# =========================================================
# 每個版本資料夾裡記錄 {專案: 檔名}。
# 用途：模組出新版時（檔名不同），提醒使用者舊版 jar 還在資料夾裡，
# 避免同一模組兩個版本並存導致 Minecraft 啟動失敗。
# 程式不會自動刪除舊檔，由使用者自行確認後移除。

def load_installed(folder: Path) -> dict[str, str]:
    path = folder / INSTALLED_FILENAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_installed(folder: Path, installed: dict[str, str]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / INSTALLED_FILENAME).write_text(
        json.dumps(installed, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def old_version_warning(
    folder: Path,
    installed: dict[str, str],
    project: str,
    new_filename: str,
) -> str | None:
    """若此專案之前記錄的檔名不同、且舊檔仍存在，回傳提醒文字。"""
    old_filename = installed.get(project)
    if old_filename and old_filename != new_filename and (folder / old_filename).exists():
        return f"舊版 {old_filename} 仍在資料夾中，請確認後手動移除，避免兩個版本衝突"
    return None


# =========================================================
# 8. 處理單一模組
# =========================================================

def required_dependency_text(version: dict[str, Any]) -> str | None:
    """回傳必要依賴的名稱清單（以逗號分隔），沒有依賴時回傳 None。"""
    required = [
        dep for dep in (version.get("dependencies") or [])
        if dep.get("dependency_type") == "required"
    ]
    if not required:
        return None

    ids = [dep["project_id"] for dep in required if dep.get("project_id")]
    names = get_project_names(ids)

    return ", ".join(
        names.get(dep.get("project_id", ""))
        or dep.get("project_id")
        or dep.get("file_name")
        or "未識別依賴"
        for dep in required
    )


def process_mod(
    mod: dict[str, Any],
    game_version: str,
    config: Config,
    folder: Path,
    installed: dict[str, str],
) -> ModResult:
    """
    處理一個模組：查詢 → 挑版本 → 略過或下載 → 檢查舊版與依賴。
    預期內的錯誤都在這裡轉成 ModResult，不會中斷整個程式。
    會直接更新 installed 字典。
    """
    project = str(mod["project"]).strip()
    label = str(mod.get("name", project))

    try:
        versions = get_project_versions(project, game_version, config.loaders)
        selected = choose_version(versions, config.version_types)

        if selected is None:
            try:
                message = explain_not_updated(project, game_version, config, versions)
            except ModrinthError:
                message = f"模組尚未更新至 Minecraft {game_version}"
            return ModResult(label, RESULT_NOT_UPDATED, message)

        file_info = choose_file(selected)
        if file_info is None:
            return ModResult(label, RESULT_ERROR, "找到版本但沒有可下載檔案")

        # 只取檔名部分，避免 API 回傳的路徑跳到其他資料夾。
        filename = Path(file_info["filename"]).name
        if not filename.lower().endswith(".jar"):
            return ModResult(label, RESULT_ERROR, f"主要檔案不是 .jar：{filename}")

        version_number = str(selected.get("version_number", "未知"))
        result = ModResult(label, RESULT_SUCCESS, "", version_number, filename)

        warning = old_version_warning(folder, installed, project, filename)
        if warning:
            result.warnings.append(warning)

        destination = folder / filename
        if destination.exists():
            result.result = RESULT_SKIPPED
            result.status = "已是最新版本，檔案已存在"
        else:
            download_file(file_info, destination)
            result.status = "下載成功，雜湊驗證通過"

        installed[project] = filename

        deps = required_dependency_text(selected)
        if deps:
            result.warnings.append(f"必要依賴請另行確認：{deps}")

        return result

    except ModrinthError as exc:
        return ModResult(label, RESULT_ERROR, str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        # API 資料缺欄位或型別不符
        return ModResult(label, RESULT_ERROR, f"API 資料格式異常：{exc!r}")


def print_result(result: ModResult) -> None:
    """在畫面上顯示單一模組的結果。"""
    prefix = {
        RESULT_SUCCESS: "下載",
        RESULT_SKIPPED: "略過",
        RESULT_NOT_UPDATED: "尚未更新",
        RESULT_ERROR: "錯誤",
    }[result.result]

    if result.filename:
        print(f"  - 版本：{result.version} / {result.filename}")
    print(f"  - {prefix}：{result.status}")
    for warning in result.warnings:
        print(f"  - 提醒：{warning}")


# =========================================================
# 9. 報告
# =========================================================

def count_by_result(results: list[ModResult]) -> dict[str, int]:
    counts = {key: 0 for key in (RESULT_SUCCESS, RESULT_SKIPPED, RESULT_NOT_UPDATED, RESULT_ERROR)}
    for r in results:
        counts[r.result] += 1
    counts["total"] = len(results)
    return counts


def write_report(
    folder: Path,
    game_version: str,
    config: Config,
    results: list[ModResult],
) -> Path:
    """將結果寫入 download_report.json，回傳報告路徑。"""
    folder.mkdir(parents=True, exist_ok=True)
    report_path = folder / REPORT_FILENAME
    report_path.write_text(
        json.dumps(
            {
                "minecraft_version": game_version,
                "loaders": config.loaders,
                "version_types": config.version_types,
                "summary": count_by_result(results),
                "results": [asdict(r) for r in results],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report_path


def print_summary(results: list[ModResult], report_path: Path) -> None:
    counts = count_by_result(results)
    total = counts["total"]

    print("\n完成。")
    print(f"成功下載：{counts[RESULT_SUCCESS]} / {total}")
    print(f"已存在略過：{counts[RESULT_SKIPPED]} / {total}")
    print(f"尚未更新：{counts[RESULT_NOT_UPDATED]} / {total}")
    print(f"發生錯誤：{counts[RESULT_ERROR]} / {total}")

    not_updated = [r for r in results if r.result == RESULT_NOT_UPDATED]
    if not_updated:
        print("\n以下模組尚未更新（不是錯誤，之後可再執行一次）：")
        for r in not_updated:
            print(f"  - {r.project}：{r.status}")

    old_versions = [
        (r.project, w) for r in results for w in r.warnings if w.startswith("舊版")
    ]
    if old_versions:
        print("\n以下模組有舊版 jar 仍在資料夾（請手動移除）：")
        for project, warning in old_versions:
            print(f"  - {project}：{warning}")

    print(f"\n報告位置：{report_path}")


# =========================================================
# 10. 主程式
# =========================================================

CANCEL_KEYS = {"q", "quit", "exit"}   # 輸入這些字（不分大小寫）就取消


def get_known_game_versions() -> set[str] | None:
    """
    向 Modrinth 取得所有 Minecraft 版本名稱，用來檢查使用者輸入。
    查詢失敗時回傳 None，呼叫端會改成只檢查格式。
    """
    try:
        data = api_get("/tag/game_version")
    except ModrinthError:
        return None
    return {
        item["version"] for item in data
        if isinstance(item, dict) and item.get("version")
    }


def ask_game_version() -> str | None:
    """
    反覆詢問 Minecraft 版本，直到輸入正確為止。
    輸入 q 或按 Ctrl+C 取消，回傳 None。
    """
    known_versions = get_known_game_versions()
    if known_versions is None:
        print("（無法取得 Modrinth 版本清單，只檢查格式）")

    while True:
        try:
            raw = input("請輸入目標 Minecraft 版本（例如 1.21.1，輸入 q 取消）：")
        except (KeyboardInterrupt, EOFError):
            print()
            return None

        # NFKC：把中文輸入法打出的全形字（例如 １．２１）轉成半形。
        version = unicodedata.normalize("NFKC", raw).strip()

        if version.lower() in CANCEL_KEYS:
            return None

        if not version:
            print("  版本不可空白，請重新輸入。")
            continue

        try:
            safe_version_folder(version)
        except ModrinthError as exc:
            print(f"  {exc}請重新輸入。")
            continue

        if known_versions is not None and version not in known_versions:
            print(f"  Modrinth 沒有 Minecraft「{version}」這個版本，請重新輸入。")
            continue

        return version


def run() -> int:
    config = load_config()
    game_version = ask_game_version()
    if game_version is None:
        print("已取消")
        return 0

    folder = config.repository_dir / game_version

    print(f"\n目標版本：Minecraft {game_version}")
    print(f"Loader：{', '.join(config.loaders)}")
    print(f"版本類型：{', '.join(config.version_types)}")
    print(f"下載位置：{folder}")
    print("只會新增檔案，不會覆蓋或刪除既有檔案。\n")

    installed = load_installed(folder)
    results: list[ModResult] = []
    total = len(config.mods)

    for index, mod in enumerate(config.mods, start=1):
        if not isinstance(mod, dict) or not mod.get("project"):
            print(f"[{index}/{total}] 略過：模組設定缺少 project。")
            results.append(ModResult("unknown", RESULT_ERROR, "設定錯誤：缺少 project"))
            continue

        print(f"[{index}/{total}] {mod.get('name', mod['project'])} ({mod['project']})")
        result = process_mod(mod, game_version, config, folder, installed)
        print_result(result)
        results.append(result)

        time.sleep(REQUEST_DELAY)

    save_installed(folder, installed)
    report_path = write_report(folder, game_version, config, results)
    print_summary(results, report_path)

    # 尚未更新、已存在都不算錯誤，正常結束回傳 0。
    return 0


if __name__ == "__main__":
    try:
        exit_code = run()
    except (ModrinthError, OSError) as exc:
        print(f"\n程式停止：{exc}", file=sys.stderr)
        exit_code = 1

    # Jupyter 中不呼叫 SystemExit，否則會多顯示一段例外訊息。
    if "ipykernel" not in sys.modules:
        raise SystemExit(exit_code)