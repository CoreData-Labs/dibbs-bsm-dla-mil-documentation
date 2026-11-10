# 📚 DIBBS BSM DLA MIL Documentation

### A friendly, automated way to collect, organize, and use publicly available DLA procurement files — built to help individuals, small businesses, researchers, and developers.

Welcome! 👋 This project downloads the ZIP archives published on the official [🏛️ DLA Internet Bid Board System (DIBBS)](https://www.dibbs.bsm.dla.mil/) **Recent RFQ Dates** page, extracts them into neat local folders, and keeps everything organized so you can search, analyze, and build on it with your own tools.

Instead of clicking through dozens of download links by hand, you run one script and let it do the repetitive work: **download a ZIP → verify it → extract it → move on to the next one.**

| At a glance        |                                                                                     |
| ------------------ | ----------------------------------------------------------------------------------- |
| 🐍 **Language**    | Python 3                                                                            |
| 🌐 **Browser**     | Chromium, controlled with [Playwright](https://playwright.dev/python/)              |
| 📥 **Downloads**   | ZIP archives listed on the official Recent RFQ Dates page                           |
| 📂 **Output**      | `dibbs_data/zips/` (original ZIPs) and `dibbs_data/extracted/` (their contents)     |
| 🔁 **Re-runnable** | Finished archives are skipped; an interrupted run simply continues where it stopped |

---

## 💡 Why this project exists

Government procurement information can be hard to work with when files are spread across pages and have to be downloaded one at a time. Large organizations can afford staff and software for that. Small businesses, independent contractors, and individual researchers usually can't — and shouldn't have to. This project exists to:

- 🏪 **Help small businesses** — collect and organize procurement-related files without manual busywork
- 👥 **Help individuals** — cut the time it takes to find and download what is available
- 🔎 **Support research** — keep files locally so they are easy to search, analyze, and reference
- 💻 **Support developers** — provide clean local data for indexing tools, document pipelines, and other applications
- 🔓 **Encourage transparency** — make it easier to work with information published on official government websites
- ⚙️ **Reduce repetitive work** — automate downloading, validating, and extracting
- 🤝 **Stay approachable** — be usable by people with different levels of technical experience

---

## 🌐 Official sources

Everything this project downloads comes from the official DLA website.

- 🌐 **DIBBS:** https://www.dibbs.bsm.dla.mil/
- 📅 **Recent RFQ Dates:** https://www.dibbs.bsm.dla.mil/RFQ/RFQDates.aspx?category=recent
- 🏛️ **Defense Logistics Agency:** https://www.dla.mil/

✅ Always consult the official website for the latest information, applicable requirements, and authoritative documents.

---

## ✨ What it does

1. 🌍 **Opens the official page** — launches a visible Chromium window and loads the Recent RFQ Dates page.
2. 📜 **Acknowledges the DoD Notice and Consent Banner** — the site shows this banner before it serves content, and the script clicks **OK** for you (see the [notice below](#-the-dod-notice-and-consent-banner)).
3. 🔗 **Finds the ZIP links** — collects every official archive link that is actually on the page.
4. 📥 **Downloads one archive at a time** — each file is written under a temporary name first, so an interruption can never leave a half-written ZIP behind.
5. 🛡️ **Verifies the download** — confirms it is a real ZIP, that the finished file is in the folder with the expected size, and that every file inside passes its integrity check.
6. 📦 **Extracts it immediately** — into its own folder under `dibbs_data/extracted/`, with protection against archives that try to write outside the destination.
7. ➡️ **Moves on to the next archive** — and prints a summary when finished.

### 🔁 Safe to stop and run again

- ⏭️ Archives that are already fully extracted are **skipped**.
- 🩹 A folder that was only **partly extracted** is detected (by comparing it with the ZIP's own file list) and repaired.
- 🗑️ A **corrupt ZIP** is deleted and downloaded fresh instead of being reused forever.
- 🔄 `bqothers.zip` is rewritten by DIBBS under the same name, so it is **downloaded again on every run**.
- ⌨️ Press `Ctrl+C` at any time. Run the script again and it carries on.

### ⚠️ Limits to be aware of

The downloader works with the archive links that are **actually available on the target page**. It does not guarantee that every historical archive, or every file on DIBBS, will be discovered. Website layouts and links can change at any time.

---

## 📜 The DoD Notice and Consent Banner

DIBBS shows a **Department of Defense (DoD) Notice and Consent Banner** that you normally accept by clicking **OK** in your browser. Because this project automates a browser, **the script clicks OK on your behalf**.

👉 Please read the banner on the official site before you run the script. **By running it, you are accepting the same conditions you would accept by clicking OK yourself.** Do not use the script if you do not agree to them.

---

## 📦 What gets downloaded

The Recent RFQ Dates page lists, for each posting date, a few downloadable files. This project downloads the **ZIP** files:

| File             | What it is                                            | Example        |
| ---------------- | ----------------------------------------------------- | -------------- |
| `ca<YYMMDD>.zip` | The daily RFQ ZIP (the page's "Zip File Name" column) | `ca261027.zip` |
| `bq<YYMMDD>.zip` | The daily Batch Quote ZIP ("Batch Quote File Name")   | `bq261027.zip` |
| `bqothers.zip`   | All other available RFQs in Batch Quote format        | `bqothers.zip` |

📅 The number in a daily file name is the posting date as `YYMMDD`. For example, `261027` is **10-27-2026**.

ℹ️ The small `in<YYMMDD>.txt` index files on the same page are not downloaded by default.

### 📂 Folder structure

After a run, your project folder looks like this:

```text
📂 dibbs-bsm-dla-mil-documentation/
├── 📄 main.py                  # 🚀 The downloader
├── 📄 README.md                # 📖 This file
└── 📂 dibbs_data/              # 🗃️ Created automatically on the first run
    ├── 📁 zips/                # 📥 Original ZIP archives, exactly as downloaded
    │   ├── bq260928.zip
    │   ├── bq261001.zip
    │   └── ...
    └── 📁 extracted/           # 📂 One folder of extracted files per ZIP
        ├── bq260928/
        ├── bq261001/
        └── ...
```

✅ Keeping the original ZIPs separate from the extracted files makes it easy to manage storage, inspect the original downloads, and re-run processing whenever you need to.

---

## 🚀 Installation

Follow these steps **in order**. They set up everything the script needs, including the Playwright-managed Chromium browser (no separate Chrome or ChromeDriver install is required).

```bash
# Install required applications
sudo apt-get install bash git ghostscript coreutils util-linux findutils grep sed gawk psmisc openssh-client ca-certificates python3 python3-pip python3-venv python3-lxml python3-psutil iputils-ping xvfb nodejs -y

# Clone the repository
git clone --depth 1 https://github.com/CoreData-Labs/dibbs-bsm-dla-mil-documentation.git

# Enter the folder
cd dibbs-bsm-dla-mil-documentation

# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Install the Python packages required by the project.
pip install -r requirements.txt

# Install the required Python packages
pip install playwright

# Install Playwright system dependencies
playwright install --with-deps

# Install Playwright Chromium
playwright install chromium

# Run the script
python3 main.py
```

### 📝 Notes on the steps

- 🐧 The `apt-get` command is for **Debian/Ubuntu-based Linux** (this includes Linux on a Chromebook). On another system, install Python 3 and Git with your package manager, then use the same virtual-environment, `pip`, and `playwright` steps.
- 🪟 On **Windows**, activate the virtual environment with `.venv\Scripts\activate` instead of `source .venv/bin/activate`.
- 🔑 The clone command uses HTTPS, so no SSH key is needed. `--depth 1` downloads only the latest version, which is faster.
- 🔁 Next time, you only need to enter the folder, activate the environment, and run the script:

  ```bash
  # Enter the folder and activate the environment
  cd dibbs-bsm-dla-mil-documentation && source .venv/bin/activate

  # Run the downloader again (finished archives are skipped)
  python3 main.py
  ```

---

## ▶️ Running the downloader

```bash
# 🚀 Start the downloader
python3 main.py
```

A Chromium window opens, accepts the banner, and the script starts working through the archives. You will see progress like this (example output — your numbers will differ):

```text
2026-10-28 13:01:35 | INFO | Opening official DIBBS Recent RFQ Dates page: https://www.dibbs.bsm.dla.mil/RFQ/RFQDates.aspx?category=recent
2026-10-28 13:01:51 | INFO | Found 49 matching RFQ ZIP link(s).
2026-10-28 13:01:51 | INFO | Processing archive URL: https://dibbs2.bsm.dla.mil/Downloads/RFQ/Archive/bq260928.zip
2026-10-28 13:01:58 | INFO | Download complete and confirmed in the folder: dibbs_data/zips/bq260928.zip (101291 bytes)
2026-10-28 13:01:58 | INFO | Extracted bq260928.zip to dibbs_data/extracted/bq260928
```

When it finishes, a **run summary** shows how many archives were downloaded, extracted, skipped, or failed, and where the folders are. The Chromium window stays open for about 30 seconds so you can look at it, then closes.

### 💡 Handy tips

| I want to…                                | Do this                                                                                         |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Stop the run                              | Press `Ctrl+C`. Run `python3 main.py` again later to continue.                                  |
| Run on a machine with no desktop (server) | Use the virtual display that was installed with `xvfb`: `xvfb-run -a python3 main.py`           |
| Get a fresh copy of one archive           | Delete its ZIP in `dibbs_data/zips/` and its folder in `dibbs_data/extracted/`, then run again. |
| Re-check everything                       | Just run the script again. Finished archives are skipped quickly.                               |

---

## 🧯 Troubleshooting

| What you see                                                | What it means                                                                                        | What to do                                                                                                         |
| ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `Attempt 1/3 did not return a ZIP … content-type text/html` | The download server answered with its notice banner page instead of the file. This is expected once. | Nothing — the script switches to browser downloads for that server automatically.                                  |
| `The browser never started a download for …`                | The banner was shown but no download followed within 60 seconds.                                     | Run the script again. If it repeats, open an issue with the `Warning banner shown at … (form action: …)` log line. |
| `Could not acknowledge the warning page automatically`      | The OK button was not found on the banner page.                                                      | Run again; if it persists, the site layout may have changed — open an issue with the logged page text.             |
| `ZIP validation failed … damaged member`                    | The downloaded archive is corrupt.                                                                   | The bad ZIP is deleted automatically. Run again to download a fresh copy.                                          |
| `Unsafe ZIP path detected`                                  | An archive contains paths that would escape the destination folder, so it was refused on purpose.    | Do not extract it manually. Open an issue so it can be reviewed.                                                   |
| `playwright: command not found` or a missing-browser error  | The virtual environment is not active, or the browser was not installed.                             | Run `source .venv/bin/activate`, then `playwright install --with-deps chromium`.                                   |
| `Found 0 matching RFQ ZIP link(s)`                          | The page loaded but had no archive links, or its layout changed.                                     | Check the page in your own browser. The script logs links that mention ZIP or RFQ to help you investigate.         |

---

## 🛠️ How to use the files

1. **Browse `dibbs_data/extracted/`** to find the files you care about.
2. **Keep the original ZIPs** in `dibbs_data/zips/` as your untouched source copies.
3. **Search** file names and contents with your favorite local tools.
4. **Organize** records by posting date (it is right there in each file name).
5. **Build on it** — feed the files into your own scripts, indexes, or analysis tools.
6. **Re-run regularly** to pick up newly posted archives without re-downloading the old ones.

### 🔍 Ideas for what to build

- 🔎 Searching file names and document contents
- 🗂️ Organizing records by date or other available metadata
- 📇 Building local indexes
- 📊 Analyzing procurement information
- 🤖 Creating document-processing or AI-assisted research workflows
- 🛠️ Developing additional tools that use appropriately accessible source material

ℹ️ These are potential uses, not a guarantee that every archive contains a particular document type or that every document can legally be redistributed.

### 🤖 Using the data with AI and search tools

Local files make good source material for search, embeddings, and retrieval workflows. If you build with them:

- ✅ Keep a reference from every result back to the original file and archive, so outputs can be traced and verified.
- ✅ Re-run the downloader regularly so your data stays current.
- ⚠️ Always confirm important details against the official DIBBS site before using anything for a real business, legal, technical, or procurement decision.
- ⚠️ Treat your local copy as a **convenience collection**, not an official system of record.
- ⚠️ Check each file's distribution statements and restrictions **before** sharing it or using it in a public tool.

---

## 🌟 Who this helps

| Who                                     | How it helps                                                                  |
| --------------------------------------- | ----------------------------------------------------------------------------- |
| 🏪 Small businesses                     | Collect and organize procurement files without hours of manual downloading    |
| 🧑‍💼 Independent contractors & suppliers  | Keep a searchable local copy of what has been posted                          |
| 💻 Developers                           | Get clean, dated local data for indexing and document-processing tools        |
| 🔬 Researchers                          | Study publicly available procurement information with a reproducible workflow |
| 👤 Individuals                          | Explore government records without clicking through every link                |
| 🧑‍🏫 Advisors & small-business counselors | Show clients a repeatable way to gather and organize this information         |
| 🌍 Communities                          | Make useful public information easier for more people to reach                |

---

## 💻 Operating system compatibility

- 🐧 **Linux (Debian/Ubuntu-based):** The installation steps above are written for this. Recommended.
- 🪟 **Windows / 🍎 macOS:** Playwright supports both, so the script can run there too — install Python 3 and Git yourself, then follow the same virtual-environment, `pip`, and `playwright` steps.
- 📂 **Just using the files?** You do not need Linux to open, search, or analyze files that have already been downloaded.
- 🛠️ Other scripts you add to this repository (for example, for compression or uploading) may need Linux-specific tools — check their own instructions.

---

## 🏘️ Ways to use this to help your community

Individual knowledge becomes community strength when it's shared:

- 📣 **Host a short info session** at a library, makerspace, or small-business group on how to find and read posted procurement files.
- 🗒️ **Write a one-page guide** that explains what the `ca`, `bq`, and `bqothers` files are, so newcomers aren't overwhelmed.
- 🧑‍🤝‍🧑 **Pair up as a peer helper** — if you've learned your way around these files, walk a neighbor or fellow business owner through it.
- 🏫 **Share with local small-business support offices** and workforce or entrepreneurship programs that regularly meet people who could use this information.
- 🤖 **Build a free local tool** — a search page or index that helps people find posted items at any hour.
- 🔁 **Pass it on** — encourage everyone you help to share the project with someone else.

None of this requires special expertise — just someone willing to learn once and explain it clearly to someone else.

---

## 🛡️ Responsible use

🤝 This project is intended to support legitimate research, organization, and use of information available through official sources.

- 📜 **Respect website rules:** Follow applicable DLA website terms, notices, access restrictions, and automation policies — including the DoD Notice and Consent Banner described above.
- 🔐 **Use authorized access:** Do not bypass authentication, access controls, or restrictions on documents.
- 🐢 **Be considerate of the website:** The script downloads one file at a time and skips finished files. Please don't modify it to hammer the site, and avoid unnecessary repeated runs.
- ⚖️ **Verify document permissions:** A file being accessible online does not automatically mean it can be freely redistributed or republished.
- 🔒 **Protect sensitive information:** Do not publish credentials, personal information, controlled technical data, or other restricted material.
- 📑 **Respect document-specific notices:** Check distribution statements, copyright notices, export-control restrictions, and other conditions before sharing files.
- 🏛️ **Prefer official sources:** When permission to redistribute is unclear, link to the official source instead of republishing the file.

---

## ⚖️ Legal and distribution notice

🏛️ This repository is an independent project and is not affiliated with, endorsed by, or sponsored by the Defense Logistics Agency, the U.S. Department of Defense, or the U.S. Government.

🎯 The project is intended to help people work with information available from official sources. It does not grant permission to access restricted materials, bypass website controls, or redistribute documents contrary to applicable restrictions.

📄 Different files may have different legal and distribution conditions. The legal status of a particular document depends on its contents, applicable law, and any relevant distribution or access restrictions.

⚠️ Before downloading, storing, publishing, or redistributing documents, you are responsible for determining whether your intended use is permitted.

🔎 The availability of a document on a public website should not be treated as blanket authorization to redistribute it.

💻 The repository's software license, if provided, applies to the project's own code according to its terms. It does not automatically apply to third-party or government documents collected using the software.

ℹ️ Nothing in this README constitutes legal advice.

---

## ⚠️ Disclaimer

📌 This project is provided on an "as is" basis, without guarantees of availability, completeness, accuracy, or suitability for a particular purpose.

🔄 Website layouts, archive links, file formats, and access requirements may change. Downloads may fail, archives may be unavailable, and extracted contents may require additional validation.

✅ Verify important information against authoritative sources before relying on it for business, legal, technical, or procurement decisions.

---

## 🤝 Contributing

🌟 Contributions, suggestions, bug reports, and improvements are welcome. You can help by:

- 🐛 Reporting problems with the downloader (please include the relevant log lines)
- 📝 Improving documentation and installation instructions
- 🛡️ Improving error handling and archive validation
- 🧹 Making the code easier to understand and maintain
- ♿ Suggesting ways to improve accessibility and usability
- 🛠️ Building tools that help people search and organize permitted materials
- 🔍 Helping ensure the project uses official sources responsibly

📜 Please make sure any contributed code, documents, or other materials can be shared legally.

---

## 📜 License

📄 See the repository's `LICENSE` file, if present, for the terms governing the project's original source code.

⚖️ Documents obtained from external websites remain subject to their own applicable legal and distribution conditions.

---

## 🔗 Useful links

- 📚 **Project repository:** https://github.com/CoreData-Labs/dibbs-bsm-dla-mil-documentation.git
- 🌐 **Official DIBBS website:** https://www.dibbs.bsm.dla.mil/
- 📅 **Recent RFQ Dates:** https://www.dibbs.bsm.dla.mil/RFQ/RFQDates.aspx?category=recent
- 🏛️ **Defense Logistics Agency:** https://www.dla.mil/

---

### 🌍 Our goal

💙 Make useful procurement information easier for everyone to access, organize, and use responsibly.

🚀 Help individuals, small businesses, developers, and researchers spend less time on repetitive tasks and more time putting useful information to work.

🤝 **Better access. Easier research. More opportunities for everyone.**
