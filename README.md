# Minecraft Tools

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

### `modrinth_downloader.py` - The Minecraft Mod Downloader (Modrinth)

The main program for the automatic mod downloader. No manual changes are required. It automatically downloads the mods specified in the `mods.json` list from Modrinth.

### `mods.json`

You can edit this file to specify which mods you want to download automatically.

### `vanillatweaks_downloader.py` - The Minecraft Texture Pack Downloader (Vanilla Tweaks)

The main program for automatically downloading resource packs. It fetches and downloads the specified resource packs from Vanilla Tweaks.
