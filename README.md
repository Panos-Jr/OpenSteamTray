# OpenSteamTray

<img width="128" height="128" alt="app" src="https://github.com/user-attachments/assets/60403a30-b3ff-47df-9b82-2ec8779bfe35" />

<br>

A lightweight Windows tray app that adds games to your Steam library on the fly. Open a game's store page in Steam, and a pop-up asks if you want to apply the manifest files — no manual copying required.

<br>

# Note

`setup.bat` currently installs **Ryuu's OpenSteamTool** by default, however these are alternatives which you may use:

- [SteamTools](https://steamtools.net)
- [OpenSteamTool](https://github.com/PandaQuQ/OpenSteamTool/releases) (fork)

# Requirements


You'll need a manifest source — **Hubcap** or **Ryuu**:

- **Hubcap** — get an API key from [hubcapmanifest.com/api-keys/stats](https://hubcapmanifest.com/api-keys/stats). The app lets you know if your key expires or is invalid, and you can set it in the tray menu.
- **Ryuu** — get an API key and set it via **Set Ryuu key…** in the tray menu. Ryuu doesn't require a key in the app for public branches if you don't have one, but it's recommended for reliability. Obtain one here: [generator.ryuu.lol/api](https://generator.ryuu.lol/api)

> **Note:** If you've used the `apply manifest` feature in [**SteamLookup**](https://github.com/Panos-Jr/SteamLookup), you shouldn't need to set the Hubcap API key in OpenSteamTray — they use the same JSON files.

<br>

# Setup

## 1. Install

Download and extract `OpenSteamTray.zip` from [Releases](https://github.com/Panos-Jr/OpenSteamTray/releases) and run `setup.bat`. Then run `OpenSteamTray.exe`; it should show up in your Windows tray.

<br>

<img width="218" height="140" alt="image" src="https://github.com/user-attachments/assets/2da5b5f4-e6b1-4444-a1f1-54cef7e2aa63" />

<br>
<br>

## 2. Choose your tool

Open the tray menu and pick the tool you'll be using under **Apply tool**:

- **Steamtools** — writes to `config\stplug-in`
- **OpenSteamTool** — writes to `config\lua`
- **Ryuu OpenSteamTool** — always uses Ryuu as the source, writes to `config\lua`, and **skips the Steam restart prompt** (OpenSteamTool picks up changes live)

<br>

<img width="480" height="430" alt="image" src="https://github.com/user-attachments/assets/7561d973-cb84-45e5-88ce-988d957e4fa8" />


<br>
<br>

## 3. Pick a manifest source

Under **Manifest source**, choose between:

- **Hubcap** — uses your Hubcap API key
- **Ryuu** — uses your Ryuu API key

Selecting **Ryuu OpenSteamTool** as the tool overrides this and always uses Ryuu.

<br>

## 4. (Optional but useful) Turn on Fallback

If the current tool + source combo fails (game not found, API error, etc.), Fallback tries the other combination automatically — then returns to your original selection. Toggle it from the tray menu:

**Fallback on failure: ON / OFF**

Useful if a game exists on one source but not the other.

If you have it enabled and say one source fails, if the other one works, you should see the game in your library.


<br>

## 5. Enable Steam Debugging

Double-check that **Steam debugging** is **ON** in the tray menu. If not, press **Enable Steam debugging** below it. Steam must be running for the monitor to work.

<br>

<img width="228" height="48" alt="image" src="https://github.com/user-attachments/assets/ec8a2284-54ad-4c18-98e1-6e883ab9bee6" />

<br>
<br>

## 6. Use it in the Steam Store

When you're using the Steam app, click on a game in the Steam Store and a pop-up should appear, asking if you want to add the manifest files for the game. This is timed, so you'll have to decide within the limit. If you press `Not now`, the game is excluded and the pop-up won't show up for that specific game again.

<br>

<img width="340" height="258" alt="image" src="https://github.com/user-attachments/assets/c010426d-0eb2-43a8-8624-113129d13c05" />

<br>
<br>

## 7. Apply manually

If a game is excluded, or the game is delisted and you can't access it in the Steam Store, you can apply it manually using **Apply manifest by App ID…**. You'll just need the App ID of the game:

<br>

<img width="238" height="397" alt="image" src="https://github.com/user-attachments/assets/8b5ccd3e-f7e5-4dc1-bf28-b30da29ca51b" />


<br>
<br>

# Menu reference

| Item | What it does |
| :--- | :--- |
| **Steam debugging: ON/OFF** | Shows whether Steam's CEF debugging port is reachable |
| **Enable Steam debugging** | Creates the marker file; restart Steam to take effect |
| **Manifest source** | Switch between **Hubcap** and **Ryuu** |
| **Fallback on failure: ON/OFF** | Retry with the other tool/source if the first attempt fails |
| **Hubcap: …** | Live stats (daily usage, key expiry) — click for details |
| **Set Hubcap key…** | Store your Hubcap API key |
| **Set Ryuu key…** | Store your Ryuu API key (saved to `config.json`) |
| **Refresh stats** | Manually refresh Hubcap stats |
| **Apply tool** | Pick Steamtools / OpenSteamTool / Ryuu OpenSteamTool |
| **Apply manifest by App ID…** | Manually apply a game by ID |
| **Applied** | List of games already applied — click one to remove it |
| **Remove game by App ID…** | Remove a single game's files |
| **Remove ALL games…** | Wipe all tracked manifest/lua files |
| **Open data folder** | Opens the app's data folder |
| **Quit** | Exit the tray app |

<br>

# Notes

- **No restart needed** when using **Ryuu OpenSteamTool** — it reloads `.lua` files live.
- With Standard OpenSteamTool or Steamtools, Steam must be restarted for the new game to appear (the app will prompt, or you can enable auto-restart).
- If a Ryuu download returns 404, the app automatically fires `/requestupdate` and `/request` for that App ID, waits a few seconds, and retries once. Some games may need a minute before they're available.
