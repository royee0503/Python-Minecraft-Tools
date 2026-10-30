# -------------------------
# Vanilla Tweaks 材質包下載器
# 依照 PACKS 清單，向 vanillatweaks.net 產生並下載
# 與原本 TaurusTweaks 材質包內容一樣的 ZIP。
# -------------------------

from __future__ import annotations
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path
from typing import Any
import requests

# -------------------------
# 1. 基本設定
# -------------------------

SITE = "https://vanillatweaks.net"

# 預設版本：直接按 Enter 就使用這個版本。
DEFAULT_VERSION = "26.3"

# 下載位置：使用者的「下載」資料夾。
DOWNLOAD_DIR = Path("~/Downloads").expanduser()

# 模擬瀏覽器送出請求，跟在網站上按「Download」一樣。
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) "
        "Gecko/20100101 Firefox/144.0"
    ),
    "Referer": f"{SITE}/picker/resource-packs/",
    "Origin": SITE,
    "X-Requested-With": "XMLHttpRequest",
}

TIMEOUT = (10, 120)
CHUNK_SIZE = 1024 * 256

# 要下載的材質包（從原本 ZIP 的 Selected Packs.txt 取出，共 125 個）。
# 想增減材質包，直接修改這個清單即可。
# 名稱要用網站內部名稱（英文、無空格），例如 NoFog、3DDoors。
PACKS = [
    "HungerBarsGoldApple", "3DBookshelves", "StickyPistonSides",
    "PixelConsistentGuardianBeam", "PixelConsistentSonicBoom",
    "PixelConsistentBeaconBeam", "PixelConsistentXPOrbs",
    "PixelConsistentWither", "PixelConsistentElderGuardian",
    "PixelConsistentGhast", "ConsistentDecorPot", "ConsistentUIFix",
    "JappaSpecIcons", "BlockOutlineRainbow", "TechnobladePigs",
    "SusSandGravel", "SmootherFont", "PingColorIndicator", "WitherHearts",
    "3DStonecutters", "3DSculkVein", "3DGlowLichen", "3DVines",
    "3DMushrooms", "3DDoors", "3DLilyPads", "3DSugarcane", "3DIronBars",
    "3DRails", "3DLadders", "3DMace", "3DPointedDripstone", "3DChains",
    "3DChiseledBookshelves", "CleanerWorldBorder", "NoFog", "LowerFire",
    "CleanTintedGlass", "CleanStainedGlass", "CleanGlass", "ArabicNumerals",
    "VisualComposterStages", "VisualCauldronStages", "CompassLodestone",
    "GroovyLevers", "DirectionalDispensersDroppers", "DirectionalHoppers",
    "MusicDiscRedstonePreview", "HungerPreview", "DifferentStems",
    "FullAgeCropMarker", "Fullbright", "BuddingAmethystBorders",
    "BetterObservers", "QuieterWolves", "QuieterVillagers", "QuieterTurtles",
    "QuieterTadpoles", "QuieterStriders", "QuieterSquids",
    "QuieterSnowGolems", "QuieterSniffers", "QuieterSheep",
    "QuieterRabbits", "QuieterPigs", "QuieterParrots", "QuieterPandas",
    "QuieterLlamas", "QuieterIronGolems", "QuieterHorses",
    "QuieterHappyGhasts", "QuieterFrogs", "QuieterFoxes", "QuieterEndermen",
    "QuieterDolphins", "QuieterCows", "QuieterCopperGolems",
    "QuieterChickens", "QuieterCats", "QuieterCamels", "QuieterBees",
    "QuieterBats", "QuieterAxolotls", "QuieterArmadillos", "QuieterAllays",
    "NoCaveSounds", "QuieterPistons", "QuieterWater",
    "QuieterNetherPortals", "QuieterFire", "QuieterMinecarts",
    "QuieterDispensersDroppers", "QuieterExplosions", "QuieterThunder",
    "QuieterRain", "ShorterTallGrass", "ShorterGrass", "BrighterNether",
    "SmoothCoarseDirt", "SmoothDirt", "SmootherStones", "SmootherOakLog",
    "CircularSunandMoon", "HDEndFlash", "GoldenSavanna", "FencierFences",
    "AshlessCampfires", "AnimatedCampfireItem", "SofterWool",
    "LessPurplePurpur", "DesaturatedResin", "SolidSlime", "SolidHoney",
    "UnbundledDriedKelp", "UnbundledHayBales", "VisibleTripwires",
    "TripwireHookFix", "PixelConsistentSigns", "HangingSignLogs",
    "ColoredGlintRainbow", "AlternateEnchantGlint",
    "UnobtrusiveScaffolding", "AccurateScaffolding",
    "FullAgeAmethystMarker", "3DAmethyst",
]


# -------------------------
# 2. 自訂錯誤類別
# -------------------------

class VanillaTweaksError(Exception):
    """預期內的錯誤（網路、版本不支援、網站回傳失敗等）。"""
    pass


# -------------------------
# 3. 輸入並檢查版本
# -------------------------

def get_supported_versions(session: requests.Session) -> list[str]:
    """
    從網站的材質包選擇頁面，讀取目前支援的版本清單。
    例如：["26.3", "26.2", "26.1", "1.21", ...]（新版本在前）

    讀取失敗時回傳空清單，之後改用「分類資料是否存在」來判斷。
    """

    try:
        response = session.get(
            f"{SITE}/picker/resource-packs/",
            timeout=TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException:
        return []

    # 版本按鈕的 HTML 長這樣：<a href='#' class='version-item'>26.2</a>
    versions = re.findall(
        r"class=['\"]version-item[^'\"]*['\"]>\s*([\d.]+)\s*</a>",
        response.text
    )

    # 去除重複，保留原本順序。
    return list(dict.fromkeys(versions))


def version_tuple(version: str) -> tuple[int, ...]:
    """把 "1.21" 轉成 (1, 21)，方便比較新舊。"""
    return tuple(int(part) for part in version.split("."))


def normalize_version(text: str) -> str:
    """
    整理使用者輸入的文字：
    - 全形轉半形（例如 ２６．３ -> 26.3）
    - 中文句號、逗號轉成點
    - 去掉前面的 v、mc、minecraft 等字
    - 去掉空白
    """

    text = unicodedata.normalize("NFKC", text).strip().lower()
    text = text.replace("。", ".").replace(",", ".").replace("，", ".")
    text = re.sub(r"^(minecraft|mc|v)\s*", "", text)
    return text.replace(" ", "")


def match_supported(version: str, supported: list[str]) -> str | None:
    """
    在支援清單中找對應的版本。

    Vanilla Tweaks 以「大版本」分類，例如：
        1.21.5 -> 1.21
        26.3.1 -> 26.3
    所以找不到時，會一層一層去掉最後的小版本號再找。
    """

    parts = version.split(".")
    while parts:
        candidate = ".".join(parts)
        if candidate in supported:
            return candidate
        parts.pop()
    return None


def ask_version(supported: list[str]) -> str | None:
    """
    讓使用者輸入 Minecraft 版本，輸入錯誤會請他重新輸入。

    - 直接按 Enter：使用最新支援的版本
    - 輸入 q：離開程式（回傳 None）
    """

    default = supported[0] if supported else DEFAULT_VERSION

    if supported:
        print(f"Vanilla Tweaks 目前支援的版本：{', '.join(supported)}")

    while True:
        try:
            raw = input(
                f"請輸入 Minecraft 版本（按 Enter = {default}，輸入 q = 離開）："
            )
        except (EOFError, KeyboardInterrupt):
            print()
            return None

        text = normalize_version(raw)

        if text == "":
            return default

        if text in {"q", "quit", "exit", "離開"}:
            return None

        # 格式檢查：只能是數字和點，例如 26.3、1.21.5。
        if not re.fullmatch(r"\d{1,3}(\.\d{1,3}){1,3}", text):
            print(f"  「{raw.strip()}」不是版本號，請輸入像 26.3 或 1.21 這樣的格式。\n")
            continue

        # 網站版本清單讀取失敗時，只做格式檢查，
        # 實際是否存在由下一步的分類資料判斷。
        if not supported:
            return text

        matched = match_supported(text, supported)

        if matched == text:
            return text

        if matched:
            print(f"  Vanilla Tweaks 的 {text} 歸在 {matched}，將使用 {matched}。")
            return matched

        # 找不到時，判斷是「還沒出」還是「太舊或不存在」。
        newest = supported[0]
        if version_tuple(text) > version_tuple(newest):
            print(
                f"  Vanilla Tweaks 還沒推出 {text} 版本，"
                f"目前最新是 {newest}。\n"
            )
        else:
            print(f"  Vanilla Tweaks 不支援 {text}，請從上面的清單選一個。\n")


# -------------------------
# 4. 取得分類資料
# -------------------------

def category_key(name: str) -> str:
    """
    把分類名稱轉成網站使用的代號。
    規則：轉小寫，英數字以外的字元都換成 "-"。
    例如 "Peace and Quiet" -> "peace-and-quiet"
    """
    return re.sub(r"[^a-z0-9]", "-", name.lower())


def get_pack_categories(
    session: requests.Session,
    version: str
) -> dict[str, str]:
    """
    下載指定版本的分類清單，
    建立「材質包名稱 -> 分類路徑」的對照表。

    子分類用 "." 連接，例如：
        QuieterWolves -> peace-and-quiet.mobs
        NoFog         -> unobtrusive
    """

    url = f"{SITE}/assets/resources/json/{version}/rpcategories.json"

    try:
        response = session.get(url, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise VanillaTweaksError(f"連線 Vanilla Tweaks 失敗：{exc}") from exc

    if response.status_code == 404:
        raise VanillaTweaksError(
            f"Vanilla Tweaks 目前沒有 {version} 版本的材質包。"
        )

    if response.status_code == 403:
        raise VanillaTweaksError(
            "網站拒絕了這次連線（403），可能被防機器人機制擋下，請稍後再試。"
        )

    try:
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise VanillaTweaksError(f"讀取分類資料失敗：{exc}") from exc

    pack_map: dict[str, str] = {}

    def walk(categories: list[dict[str, Any]], path: list[str]) -> None:
        """遞迴走訪分類與子分類。"""
        for category in categories:
            current = path + [category_key(category["category"])]

            for pack in category.get("packs", []):
                pack_map[pack["name"]] = ".".join(current)

            if category.get("categories"):
                walk(category["categories"], current)

    walk(data.get("categories", []), [])

    if not pack_map:
        raise VanillaTweaksError("分類資料是空的，無法繼續。")

    return pack_map


# -------------------------
# 5. 請網站產生 ZIP
# -------------------------

def request_zip(
    session: requests.Session,
    version: str,
    selected: dict[str, list[str]]
) -> str:
    """
    把選好的材質包送給網站，
    網站會即時打包，並回傳下載連結。
    """

    url = f"{SITE}/assets/server/zipresourcepacks.php"

    try:
        response = session.post(
            url,
            data={
                "packs": json.dumps(selected),
                "version": version,
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        result = json.loads(response.text)

    except requests.RequestException as exc:
        raise VanillaTweaksError(f"請網站打包失敗：{exc}") from exc

    except ValueError as exc:
        raise VanillaTweaksError(
            "網站回傳的內容不是 JSON，可能被防機器人機制擋下。"
        ) from exc

    if result.get("status") != "success" or not result.get("link"):
        raise VanillaTweaksError(
            f"網站打包失敗：{result.get('message', result)}"
        )

    return SITE + result["link"]


# -------------------------
# 6. 下載 ZIP
# -------------------------

def unique_path(path: Path) -> Path:
    """
    如果檔案已存在，就在檔名後面加 (1)、(2)…，避免覆蓋舊檔。
    """
    if not path.exists():
        return path

    number = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({number}){path.suffix}")
        if not candidate.exists():
            return candidate
        number += 1


def download_zip(
    session: requests.Session,
    url: str,
    destination: Path
) -> Path:
    """
    串流下載 ZIP，先存成 .part 暫存檔，
    確認是有效的 ZIP 之後才改成正式檔名。
    """

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination = unique_path(destination)
    temp_path = destination.with_name(destination.name + ".part")

    try:
        with session.get(url, stream=True, timeout=TIMEOUT) as response:
            response.raise_for_status()

            with temp_path.open("wb") as output:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        output.write(chunk)

        if not zipfile.is_zipfile(temp_path):
            raise VanillaTweaksError("下載的檔案不是有效的 ZIP。")

        temp_path.rename(destination)
        return destination

    except requests.RequestException as exc:
        raise VanillaTweaksError(f"下載 ZIP 失敗：{exc}") from exc

    finally:
        temp_path.unlink(missing_ok=True)


# -------------------------
# 7. 檢查 ZIP 內容
# -------------------------

def read_selected_packs(zip_path: Path) -> list[str]:
    """
    讀取 ZIP 內的 Selected Packs.txt，
    取得實際打包進去的材質包名稱。
    """

    with zipfile.ZipFile(zip_path) as archive:
        try:
            text = archive.read("Selected Packs.txt").decode("utf-8")
        except KeyError:
            return []

    # 只取 "Combined packs:" 之前、以 Tab 開頭的行。
    main_part = text.split("Combined packs:")[0]
    return [
        line.strip()
        for line in main_part.splitlines()
        if line.startswith("\t")
    ]


# -------------------------
# 8. 主程式
# -------------------------

def run() -> int:
    with requests.Session() as session:
        session.headers.update(HEADERS)

        # 步驟 0：讀取網站支援的版本，再讓使用者輸入。
        supported = get_supported_versions(session)
        version = ask_version(supported)

        if version is None:
            print("已取消。")
            return 0

        print(f"\n目標版本：Minecraft {version}")
        print(f"材質包數量：{len(PACKS)}")
        print(f"下載位置：{DOWNLOAD_DIR}\n")

        # 步驟 1：取得這個版本有哪些材質包。
        print("1. 讀取分類資料…")
        pack_map = get_pack_categories(session, version)

        # 步驟 2：依分類整理要送出的資料；
        # 這個版本沒有的材質包列為「尚未更新」，不算錯誤。
        selected: dict[str, list[str]] = {}
        not_available: list[str] = []

        for name in PACKS:
            key = pack_map.get(name)
            if key is None:
                not_available.append(name)
                continue
            selected.setdefault(key, []).append(name)

        available_count = len(PACKS) - len(not_available)
        print(f"   可用：{available_count} 個，尚未更新：{len(not_available)} 個")

        if not selected:
            raise VanillaTweaksError("清單中的材質包在這個版本都沒有。")

        # 步驟 3：請網站打包。
        print("2. 請網站產生 ZIP…")
        link = request_zip(session, version, selected)

        # 步驟 4：下載。
        print("3. 下載中…")
        zip_path = download_zip(
            session,
            link,
            DOWNLOAD_DIR / f"VanillaTweaks_MC{version}.zip"
        )

    # 步驟 5：檢查 ZIP 內容是否完整。
    packed = read_selected_packs(zip_path)
    missing_in_zip = [
        name for name in PACKS
        if name not in not_available and name not in packed
    ]

    print("\n完成。")
    print(f"檔案位置：{zip_path}")
    print(f"ZIP 內含材質包：{len(packed)} / {len(PACKS)}")

    if not_available:
        print(f"\n以下材質包在 {version} 尚未更新（不是錯誤）：")
        for name in not_available:
            print(f"  - {name}")

    if missing_in_zip:
        print("\n注意：以下材質包有送出，但 ZIP 裡沒有：")
        for name in missing_in_zip:
            print(f"  - {name}")

    return 0


# -------------------------
# 9. 程式進入點
# -------------------------

if __name__ == "__main__":

    try:
        exit_code = run()

    except (VanillaTweaksError, OSError) as exc:
        print(f"\n程式停止：{exc}", file=sys.stderr)
        exit_code = 1

    except KeyboardInterrupt:
        # 使用者按 Ctrl+C 中斷。
        print("\n已中斷。")
        exit_code = 130

    # 在 Jupyter Notebook 中執行時不呼叫 SystemExit，
    # 避免多出一段例外訊息。
    if "ipykernel" not in sys.modules:
        raise SystemExit(exit_code)
