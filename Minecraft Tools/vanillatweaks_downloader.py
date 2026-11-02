# -------------------------
# Vanilla Tweaks 材質包下載器
# 依照材質包清單（PACKS_26_3 / PACKS_1_21_11，會依版本自動挑一份），
# 向 vanillatweaks.net 產生並下載與原本 TaurusTweaks 材質包內容一樣的 ZIP。
#
# 使用方式：
#   1. 執行程式，畫面會列出 Vanilla Tweaks 目前有的版本。
#   2. 輸入要下載的 Minecraft 版本，例如 1.21.4、1.21.11、26.3。
#      小版本會自動歸到大版本（1.21.1 ~ 1.21.11 都使用 1.21）。
#   3. 不輸入、直接按 Enter = 最新版本；按 Q = 取消程式。
# -------------------------

from __future__ import annotations
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path
from typing import Any, Callable
import requests

try:
    import msvcrt  # 只有 Windows 有：可以「按一個鍵就立刻反應」
except ImportError:
    msvcrt = None

# -------------------------
# 1. 基本設定
# -------------------------

SITE = "https://vanillatweaks.net"

# 備用版本：只有「讀不到網站版本清單」時，按 Enter 才會用到。
# 平常按 Enter 用的是網站上目前最新的版本，不需要手動更新這裡。
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

# 輸入版本時最多接受幾個字元，避免亂打一大串。
MAX_INPUT_LEN = 12

# 版本號格式：主版本.次版本，後面可以再加一段小版本。
# 例如 26.3、1.21、1.21.4、1.21.11、26.1.2
VERSION_PATTERN = re.compile(r"\d{1,2}\.\d{1,2}(\.\d{1,2})?")

# 輸入這些字就是取消（用 Enter 送出時）。
CANCEL_WORDS = {"q", "quit", "exit", "離開", "取消"}

# 要下載的材質包清單。程式會依照你選的版本，自動挑對應的那一份：
#   - 26.x 以後（26.1、26.2、26.3，以及之後出現的新版本）→ PACKS_26_3
#   - 1.21 及更舊的版本                                    → PACKS_1_21_11
# 兩份清單分別從原本 ZIP 的 Selected Packs.txt 取出：
#   TaurusTweaks_MC26.3_Survival_Server.zip    （125 個）
#   TaurusTweaks_MC1.21.11_Survival_Server.zip （122 個）
# 想增減材質包，直接修改對應的清單即可。
# 名稱要用網站內部名稱（英文、無空格），例如 NoFog、3DDoors。
# 某個版本還沒有的材質包，程式會列為「尚未更新」，不會當成錯誤。

PACKS_26_3 = [
    "UnbundledHayBales", "StickyPistonSides", "3DBookshelves",
    "HungerBarsGoldApple", "UnbundledDriedKelp", "SolidHoney", "SolidSlime",
    "DesaturatedResin", "LessPurplePurpur", "SofterWool",
    "AnimatedCampfireItem", "AshlessCampfires", "FencierFences",
    "GoldenSavanna", "HDEndFlash", "CircularSunandMoon", "SmootherOakLog",
    "SmootherStones", "SmoothDirt", "SmoothCoarseDirt", "BrighterNether",
    "ShorterGrass", "ShorterTallGrass", "QuieterRain", "QuieterThunder",
    "QuieterExplosions", "QuieterDispensersDroppers", "QuieterMinecarts",
    "QuieterFire", "QuieterNetherPortals", "QuieterWater", "QuieterPistons",
    "NoCaveSounds", "QuieterAllays", "QuieterArmadillos", "QuieterAxolotls",
    "QuieterBats", "QuieterBees", "QuieterCamels", "QuieterCats",
    "QuieterChickens", "QuieterCopperGolems", "QuieterCows",
    "QuieterDolphins", "QuieterEndermen", "QuieterFoxes", "QuieterFrogs",
    "QuieterHappyGhasts", "QuieterHorses", "QuieterIronGolems",
    "QuieterLlamas", "QuieterPandas", "QuieterParrots", "QuieterPigs",
    "QuieterRabbits", "QuieterSheep", "QuieterSniffers",
    "QuieterSnowGolems", "QuieterSquids", "QuieterStriders",
    "QuieterTadpoles", "QuieterTurtles", "QuieterVillagers",
    "QuieterWolves", "CleanGlass", "CleanStainedGlass", "CleanTintedGlass",
    "LowerFire", "NoFog", "CleanerWorldBorder", "WitherHearts",
    "PingColorIndicator", "SmootherFont", "SusSandGravel",
    "TechnobladePigs", "BlockOutlineRainbow", "JappaSpecIcons",
    "ConsistentUIFix", "ConsistentDecorPot", "PixelConsistentGhast",
    "PixelConsistentElderGuardian", "PixelConsistentWither",
    "PixelConsistentXPOrbs", "PixelConsistentBeaconBeam",
    "PixelConsistentSonicBoom", "PixelConsistentGuardianBeam",
    "BetterObservers", "BuddingAmethystBorders", "Fullbright",
    "FullAgeCropMarker", "DifferentStems", "HungerPreview",
    "MusicDiscRedstonePreview", "DirectionalHoppers",
    "DirectionalDispensersDroppers", "GroovyLevers", "CompassLodestone",
    "VisualCauldronStages", "VisualComposterStages", "ArabicNumerals",
    "3DChiseledBookshelves", "3DChains", "3DPointedDripstone", "3DMace",
    "3DLadders", "3DRails", "3DIronBars", "3DSugarcane", "3DLilyPads",
    "3DDoors", "3DMushrooms", "3DVines", "3DGlowLichen", "3DSculkVein",
    "3DStonecutters", "VisibleTripwires", "TripwireHookFix",
    "PixelConsistentSigns", "HangingSignLogs", "ColoredGlintRainbow",
    "AlternateEnchantGlint", "UnobtrusiveScaffolding",
    "AccurateScaffolding", "FullAgeAmethystMarker", "3DAmethyst",
]

PACKS_1_21_11 = [
    "HungerBarsGoldApple", "JappaSpecIcons", "ConsistentUIFix",
    "ConsistentDecorPot", "PixelConsistentGhast",
    "PixelConsistentElderGuardian", "PixelConsistentWither",
    "PixelConsistentXPOrbs", "PixelConsistentBeaconBeam",
    "PixelConsistentSonicBoom", "PixelConsistentGuardianBeam",
    "IronBarsFix", "ItemHoldFix", "CloudFogFix", "SusSandGravel",
    "TechnobladePigs", "ColoredHotbarSelOrange", "SmootherFont",
    "WitherHearts", "3DBookshelves", "3DChiseledBookshelves", "3DChains",
    "3DPointedDripstone", "3DMace", "3DLadders", "3DRails", "3DIronBars",
    "3DSugarcane", "3DLilyPads", "3DMushrooms", "3DVines", "3DGlowLichen",
    "3DStonecutters", "UnobtrusiveRain", "CleanGlass", "CleanStainedGlass",
    "CleanTintedGlass", "LowerFire", "NoFog", "CleanerWorldBorder",
    "BuddingAmethystBorders", "Fullbright", "HungerPreview",
    "MusicDiscRedstonePreview", "StickyPistonSides", "DirectionalHoppers",
    "DirectionalDispensersDroppers", "GroovyLevers", "CompassLodestone",
    "VisualCauldronStages", "VisualComposterStages", "ArabicNumerals",
    "QuieterAllays", "QuieterArmadillos", "QuieterAxolotls", "QuieterBats",
    "QuieterBees", "QuieterCamels", "QuieterCats", "QuieterChickens",
    "QuieterCopperGolems", "QuieterCows", "QuieterDolphins",
    "QuieterEndermen", "QuieterFish", "QuieterFoxes", "QuieterFrogs",
    "QuieterGoats", "QuieterHorses", "QuieterIronGolems", "QuieterPandas",
    "QuieterParrots", "QuieterPhantoms", "QuieterPigs", "QuieterPolarBears",
    "QuieterRabbits", "QuieterSheep", "QuieterSniffers",
    "QuieterSnowGolems", "QuieterSquids", "QuieterVillagers",
    "QuieterWolves", "QuieterRain", "QuieterThunder", "QuieterFire",
    "QuieterNetherPortals", "QuieterWater", "QuieterPistons",
    "NoCaveSounds", "VariatedMushroomBlocks", "CircularSunandMoon",
    "HDEndFlash", "SmootherOakLog", "BrighterNether", "ShorterGrass",
    "ShorterTallGrass", "UnbundledHayBales", "SolidHoney", "SolidSlime",
    "SofterWool", "AnimatedCampfireItem", "AshlessCampfires",
    "FencierFences", "VisibleTripwires", "TripwireHookFix",
    "UniversalLushGrass", "GoldenSavanna", "FullAgeCropMarker",
    "DifferentStems", "JappaObserver", "BetterObservers",
    "ColoredGlintRainbow", "AlternateEnchantGlint",
    "UnobtrusiveScaffolding", "AccurateScaffolding", "3DTiles", "3DDoors",
    "FullAgeAmethystMarker", "3DAmethyst", "SmootherWarpedPlanks",
    "PixelConsistentSigns", "HangingSignLogs",
]

# 清單選用規則：版本 >= 前面的數字，就用那一份（由新到舊，第一個符合的）。
PACK_SETS = [
    ((26, 0), "TaurusTweaks 26.3 版", PACKS_26_3),
    ((0, 0), "TaurusTweaks 1.21.11 版", PACKS_1_21_11),
]


# -------------------------
# 2. 自訂錯誤類別
# -------------------------

class VanillaTweaksError(Exception):
    """預期內的錯誤（網路、網站回傳失敗等）。"""
    pass


class VersionNotFoundError(VanillaTweaksError):
    """網站沒有這個版本的資料（可以請使用者重新輸入）。"""
    pass


# -------------------------
# 3. 輸入並檢查版本
# -------------------------

def get_supported_versions(session: requests.Session) -> list[str]:
    """
    從網站的材質包選擇頁面，讀取目前支援的版本清單。
    例如：["26.3", "26.2", "26.1", "1.21", ...]

    清單是每次執行時即時從網站讀的，網站新增版本（例如 26.4）
    不用改程式就會自動出現。

    讀取失敗時回傳空清單；這時程式會改成直接向網站探測版本，
    所以讀不到清單並不會讓下載失敗。
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
    # 這裡放寬一點：class 裡有 version-item 就算，後面有其他屬性也可以。
    versions = re.findall(
        r"class=['\"][^'\"]*version-item[^'\"]*['\"][^>]*>\s*([\d.]+)\s*</a>",
        response.text
    )

    # 只保留長得像版本號的字串，並去除重複、保留原本順序。
    versions = [v for v in versions if re.fullmatch(r"\d+(\.\d+)+", v)]
    return list(dict.fromkeys(versions))


def version_tuple(version: str) -> tuple[int, ...]:
    """把 "1.21" 轉成 (1, 21)，方便比較新舊。"""
    return tuple(int(part) for part in version.split(".") if part.isdigit())


def pick_pack_set(version: str) -> tuple[str, list[str]]:
    """
    依版本挑要下載的材質包清單，回傳 (清單名稱, 材質包名稱列表)。

    26.x 以後（含之後出現的新版本）用 26.3 的清單；
    1.21 及更舊的用 1.21.11 的清單。
    清單裡網站該版本沒有的包，之後會列為「尚未更新」，不算錯誤。
    """

    current = version_tuple(version)
    for minimum, label, packs in PACK_SETS:
        if current >= minimum:
            return label, packs
    return PACK_SETS[-1][1], PACK_SETS[-1][2]


def normalize_version(text: str) -> str:
    """
    整理使用者輸入的文字：
    - 全形轉半形（例如 ２６．３ -> 26.3）
    - 中文句號、逗號轉成點
    - 去掉前面的 v、mc、minecraft 等字
    - 去掉空白
    - 1.21.x、1.21.* 視為 1.21（代表任何小版本）
    """

    text = unicodedata.normalize("NFKC", text).strip().lower()
    text = text.replace("。", ".").replace(",", ".").replace("，", ".")
    text = re.sub(r"^(minecraft|mc|v)\s*", "", text)
    text = text.replace(" ", "")
    return re.sub(r"\.(x|\*)$", "", text)


def version_candidates(version: str) -> list[str]:
    """
    列出可能的版本，越精確越前面。

    Vanilla Tweaks 以「大版本」分類（網站上只有 1.21，沒有 1.21.4），
    所以要一層一層去掉最後的小版本號再找：
        1.21.11 -> ["1.21.11", "1.21"]
        26.3.1  -> ["26.3.1", "26.3"]
        26.3    -> ["26.3"]
    至少保留兩段（主版本.次版本），不會退到只剩 "1"。
    """

    parts = version.split(".")
    candidates = []
    while len(parts) >= 2:
        candidates.append(".".join(parts))
        parts.pop()
    return candidates


# ---- 讀取使用者輸入（支援「按 Q 立刻取消」）----

# 按鍵模式下，只接受這些字元，其他按鍵直接忽略。
ALLOWED_KEYS = set("0123456789.x*")


def stdin_is_terminal() -> bool:
    """鍵盤輸入是不是接在真正的終端機上？"""
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def hotkey_available() -> bool:
    """
    是不是能「按一個鍵就立刻反應」？
    目前只有 Windows 的終端機可以（cmd、PowerShell、Windows Terminal、
    VS Code 終端機）。IDLE、Jupyter 等環境會自動改用一般輸入，
    這時要輸入 q 再按 Enter 才會取消。
    """

    try:
        return (
            msvcrt is not None
            and sys.stdin is not None
            and sys.stdin.isatty()
        )
    except (AttributeError, ValueError):
        return False


def _key_to_char(key: str) -> str:
    """把按下的鍵整理成小寫單一字元：全形轉半形，中文句點、逗號轉成「.」。"""
    key = unicodedata.normalize("NFKC", key).lower()
    if key in {"。", ",", "，"}:
        return "."
    return key


def _drain_keys() -> None:
    """
    清掉還沒被讀走的按鍵。

    例如連續打 qwer：Q 一按就取消程式，後面的 w、e、r 如果不清掉，
    會跑到 PowerShell / cmd 的命令列去，變成「無法辨識 'wer'」的錯誤。
    """

    try:
        while msvcrt.kbhit():
            msvcrt.getwch()
    except (OSError, AttributeError):
        pass


def read_line_hotkey(
    prompt: str,
    getkey: Callable[[], str] | None = None
) -> str | None:
    """一個鍵一個鍵讀取輸入，並在結束時清掉多打的按鍵。詳見 _read_keys。"""

    try:
        return _read_keys(prompt, getkey or msvcrt.getwch)
    finally:
        _drain_keys()


def _read_keys(prompt: str, getkey: Callable[[], str]) -> str | None:
    """
    一個鍵一個鍵讀取輸入。

    - 一開始就按 Q（大小寫、全形都可以）：立刻取消，不用按 Enter，回傳 None
    - 只接受數字、小數點、x、*，其他按鍵直接忽略（防止亂輸入）
    - Backspace 可以刪除；Enter 送出；Ctrl+C 取消
    """

    print(prompt, end="", flush=True)
    buffer: list[str] = []

    while True:
        key = getkey()

        # 方向鍵、功能鍵會送出兩個碼，第二個碼也要讀掉。
        if key in ("\x00", "\xe0"):
            getkey()
            continue

        # Ctrl+C
        if key == "\x03":
            print()
            return None

        # Enter
        if key in ("\r", "\n"):
            print()
            return "".join(buffer)

        # Backspace
        if key == "\x08":
            if buffer:
                buffer.pop()
                print("\b \b", end="", flush=True)
            continue

        char = _key_to_char(key)

        # 還沒輸入任何字就按 Q：直接取消。
        if char == "q" and not buffer:
            print(char)
            return None

        if char in ALLOWED_KEYS and len(buffer) < MAX_INPUT_LEN:
            buffer.append(char)
            print(char, end="", flush=True)


def read_input(prompt: str) -> str | None:
    """讀取一行輸入。回傳 None 代表使用者要取消（Q、Ctrl+C、Ctrl+D）。"""

    if hotkey_available():
        return read_line_hotkey(prompt)

    try:
        return input(prompt)
    except EOFError:
        print()
        if not stdin_is_terminal():
            print(
                "偵測不到鍵盤輸入（目前的執行環境無法輸入文字）。\n"
                "請在 PowerShell、cmd 或 VS Code 的「終端機」裡，"
                "用 python 執行這支程式。"
            )
        return None
    except KeyboardInterrupt:
        print()
        return None


def show_supported_versions(supported: list[str]) -> None:
    """列出 Vanilla Tweaks 目前有的版本（新的在前）。"""

    ordered = sorted(supported, key=version_tuple, reverse=True)
    print("Vanilla Tweaks 目前有的版本：")
    print("  " + "、".join(ordered))
    print("小版本會自動歸到對應的大版本，不用特別挑。")

    if "1.21" in supported:
        print("例如 1.21.1 ~ 1.21.11 都是 1.21.x，會使用 1.21 的材質包。")

    print()


def ask_version(supported: list[str]) -> str | None:
    """
    讓使用者輸入 Minecraft 版本。

    - 不輸入、直接按 Enter：使用最新版本
    - 按 Q：取消程式（回傳 None）
    - 格式不對會請他重新輸入。這裡只檢查「格式」，
      版本是否真的存在，交給 resolve_version 去向網站確認。
    """

    if supported:
        default = max(supported, key=version_tuple)
        show_supported_versions(supported)
        prompt = (
            f"請輸入要下載的版本"
            f"（不輸入、直接按 Enter = 最新版 {default}；按 Q = 取消）："
        )
    else:
        default = DEFAULT_VERSION
        prompt = (
            f"請輸入要下載的版本"
            f"（讀不到最新版資訊，直接按 Enter = 備用版本 {default}；"
            f"按 Q = 取消）："
        )

    while True:
        raw = read_input(prompt)

        if raw is None:
            return None

        text = normalize_version(raw)

        if text in CANCEL_WORDS:
            return None

        if text == "":
            print(f"  沒有輸入版本，使用最新版本 {default}。")
            return default

        if not VERSION_PATTERN.fullmatch(text):
            shown = raw.strip()[:20]
            print(
                f"  「{shown}」格式不對。請只輸入數字和小數點，"
                f"例如 26.3 或 1.21.4。\n"
            )
            continue

        return text


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

    網站沒有這個版本時（404）丟出 VersionNotFoundError。
    """

    url = f"{SITE}/assets/resources/json/{version}/rpcategories.json"

    try:
        response = session.get(url, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise VanillaTweaksError(f"連線 Vanilla Tweaks 失敗：{exc}") from exc

    if response.status_code == 404:
        raise VersionNotFoundError(
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


def resolve_version(
    session: requests.Session,
    requested: str,
    supported: list[str]
) -> tuple[str, dict[str, str]]:
    """
    把使用者輸入的版本，對應到網站實際有資料的版本。

    - 網站版本清單裡有的，優先嘗試（1.21.4 -> 直接用 1.21，不浪費請求）
    - 清單沒列到、或讀不到清單時，改成直接向網站確認（404 就退一層）
    這樣網站日後新增版本、或版本清單格式變了，都不會讓程式壞掉。

    回傳 (實際使用的版本, 材質包分類對照表)。
    """

    candidates = version_candidates(requested)
    known = [c for c in candidates if c in supported]
    others = [c for c in candidates if c not in supported]

    for candidate in known + others:
        try:
            return candidate, get_pack_categories(session, candidate)
        except VersionNotFoundError:
            continue

    if supported:
        hint = f"目前有的版本：{'、'.join(supported)}"
    else:
        hint = "（也讀不到網站的版本清單，可能是網站暫時擋下連線）"

    raise VersionNotFoundError(
        f"Vanilla Tweaks 找不到 {requested} 的材質包資料，請重新輸入。{hint}"
    )


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

        # 步驟 0：讀取網站目前有的版本，列出來讓使用者輸入。
        supported = get_supported_versions(session)

        if not supported:
            print("提醒：讀不到網站的版本清單，改成直接向網站確認版本。\n")

        # 輸入版本 -> 向網站確認；找不到就請使用者重新輸入。
        while True:
            requested = ask_version(supported)

            if requested is None:
                print("已取消。")
                return 0

            try:
                version, pack_map = resolve_version(
                    session, requested, supported
                )
                break
            except VersionNotFoundError as exc:
                print(f"  {exc}\n")

        if version != requested:
            print(
                f"  {requested} 屬於 {version}.x，"
                f"將使用 Vanilla Tweaks 的 {version} 材質包。"
            )

        print(f"\n目標版本：Minecraft {requested}（Vanilla Tweaks 分類：{version}）")
        pack_label, packs = pick_pack_set(version)
        print(f"材質包清單：{pack_label}（{len(packs)} 個）")
        print(f"下載位置：{DOWNLOAD_DIR}\n")

        # 步驟 1：分類資料已在上面讀取完成。
        print("1. 分類資料讀取完成。")

        # 步驟 2：依分類整理要送出的資料；
        # 這個版本沒有的材質包列為「尚未更新」，不算錯誤。
        selected: dict[str, list[str]] = {}
        not_available: list[str] = []

        for name in packs:
            key = pack_map.get(name)
            if key is None:
                not_available.append(name)
                continue
            selected.setdefault(key, []).append(name)

        available_count = len(packs) - len(not_available)
        print(f"   可用：{available_count} 個，尚未更新：{len(not_available)} 個")

        if not selected:
            raise VanillaTweaksError("清單中的材質包在這個版本都沒有。")

        # 步驟 3：請網站打包（用實際對應到的版本，例如 1.21）。
        print("2. 請網站產生 ZIP…")
        link = request_zip(session, version, selected)

        # 步驟 4：下載。檔名使用你輸入的版本，方便辨認。
        print("3. 下載中…")
        zip_path = download_zip(
            session,
            link,
            DOWNLOAD_DIR / f"VanillaTweaks_MC{requested}.zip"
        )

    # 步驟 5：檢查 ZIP 內容是否完整。
    packed = read_selected_packs(zip_path)
    missing_in_zip = [
        name for name in packs
        if name not in not_available and name not in packed
    ]

    print("\n完成。")
    print(f"檔案位置：{zip_path}")
    print(f"ZIP 內含材質包：{len(packed)} / {len(packs)}")

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
        print("\n已取消。")
        exit_code = 130

    # 在 Jupyter Notebook 中執行時不呼叫 SystemExit，
    # 避免多出一段例外訊息。
    if "ipykernel" not in sys.modules:
        raise SystemExit(exit_code)