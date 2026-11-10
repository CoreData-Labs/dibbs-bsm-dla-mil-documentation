# =====================================================================
# IMPORTS
# =====================================================================
import asyncio  # Provide asynchronous execution for Playwright.
import http.client  # Exception types for broken HTTP transfers.
import logging  # Record progress, warnings, and errors in the console.
import re  # Clean URL filenames and parse Content-Range headers.
import time  # Measure download speed and stalls.
import urllib.error  # HTTP and URL errors from the streaming downloader.
import urllib.request  # Standard-library streaming downloader (no extra dependency).
import zipfile  # Only used to confirm a downloaded file is a ZIP (nothing is extracted).
from dataclasses import dataclass  # Build the small counter class without boilerplate.
from pathlib import Path  # Work with local filesystem paths.
from typing import List, Optional, Tuple  # Annotate lists, optional values, and tuples.
from urllib.parse import unquote, urlparse  # Safely interpret URL paths and hostnames.
from playwright.async_api import (  # Control visible Chromium and handle browser errors.
    Error as PlaywrightError,  # Base class of every Playwright error, timeouts included.
    TimeoutError as PlaywrightTimeoutError,  # Error raised when a browser wait times out.
    async_playwright,  # Entry point that starts Playwright.
)

# =====================================================================
# CONFIGURATION
# =====================================================================
START_URL = "https://www.dibbs.bsm.dla.mil/RFQ/RFQDates.aspx?category=recent"  # Official Recent RFQ Dates page.
ALLOWED_HOSTS = {  # Limit downloads to official DIBBS hosts.
    "dibbs2.bsm.dla.mil",  # Host that serves the archive downloads.
    "www.dibbs.bsm.dla.mil",  # Main DIBBS website host.
    "dibbs.bsm.dla.mil",  # Bare DIBBS domain.
}
ARCHIVE_PATH_MARKER = "/Downloads/RFQ/Archive/"  # Official RFQ archive download path.
ZIP_DIR = Path("zip")  # Store downloaded ZIP archives here (they stay zipped).
TIMEOUT_MS = 20000  # Standard browser operation timeout in milliseconds.

# Direct streaming download (the main path).
HTTP_READ_TIMEOUT_S = (
    60  # A connection that sends nothing for this long counts as dropped.
)
CHUNK_SIZE = 1024 * 1024  # Read and write 1 MB at a time.
RANGE_CHUNK_BYTES = (
    64 * 1024 * 1024
)  # Size of each ranged request (about 16 seconds at 4 MB/s).
MAX_NO_PROGRESS_ATTEMPTS = (
    5  # Ranged mode: give up after this many requests in a row that add no bytes.
)
MAX_FULL_ATTEMPTS = 20  # Whole-file mode: restart from zero at most this many times.
FULL_RETRY_DELAY_S = 10  # Pause between whole-file restarts.

# Browser download (consent step and last-resort fallback).
MAX_BROWSER_ATTEMPTS = 3  # Try each fallback browser download at most this many times.
BROWSER_DOWNLOAD_TIMEOUT_S = 60  # Seconds to wait for the browser to START a download.
BROWSER_SAVE_MAX_S = 7200  # Hard cap per browser download (two hours).
STALL_TIMEOUT_S = (
    180  # Cancel a browser download whose bytes stop growing for this long.
)
PROGRESS_POLL_S = 5  # How often to check browser download progress.
PROGRESS_LOG_S = 30  # How often to log download progress.
BROWSER_DOWNLOAD_DIR = Path("zip_tmp")  # Where Chromium stages in-progress downloads.

# =====================================================================
# LOGGING
# =====================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("dibbs_downloader")


# =====================================================================
# DATA HOLDERS
# =====================================================================
@dataclass
class RunStats:  # Hold the counters that appear in the run summary.
    downloaded: int = 0  # New ZIP files saved during this run.
    skipped: int = 0  # ZIP files that were already on disk and valid.
    failed: int = 0  # Archives that could not be downloaded.
    failed_requests: int = 0  # Failed browser network requests (real failures only).


# =====================================================================
# URL HELPERS
# =====================================================================
def filename_from_url(
    url: str,
) -> str:  # Extract the archive filename, e.g. bq261001.zip.
    raw_name = unquote(
        Path(urlparse(url).path).name
    )  # Last URL path part, URL-decoded.
    cleaned_name = re.sub(
        r"[^A-Za-z0-9._-]", "_", raw_name
    )  # Replace unsafe characters.
    return cleaned_name.strip(".") or "download.zip"  # Never return an empty name.


def is_allowed_archive_url(
    url: str,
) -> bool:  # Check for an expected official ZIP archive URL.
    parsed = urlparse(url)
    host_allowed = (parsed.hostname or "").lower() in ALLOWED_HOSTS
    path_allowed = ARCHIVE_PATH_MARKER.lower() in parsed.path.lower()
    zip_allowed = parsed.path.lower().endswith(".zip")
    return parsed.scheme == "https" and host_allowed and path_allowed and zip_allowed


# =====================================================================
# BROWSER PAGE HANDLING
# =====================================================================
async def acknowledge_warning(
    page,
) -> bool:  # Find and click the warning page's OK control.
    logger.info("Checking whether the DIBBS warning page needs acknowledgement.")
    candidates = [
        page.locator("#butAgree"),  # The DIBBS banner's own OK button.
        page.get_by_role("button", name="OK", exact=True),
        page.locator('input[type="submit"][value="OK" i]'),
        page.locator('input[type="button"][value="OK" i]'),
        page.get_by_role("link", name="OK", exact=True),
        page.get_by_text("OK", exact=True),
    ]
    for candidate in candidates:
        try:
            match_count = await candidate.count()
            for index in range(
                match_count
            ):  # The first match may be hidden, so check all.
                control = candidate.nth(index)
                if not await control.is_visible():
                    continue
                logger.info("Found a visible OK control; clicking it.")
                await control.click(timeout=5000, no_wait_after=True)
                try:  # Wait for the browser to leave the warning page.
                    await page.wait_for_url(
                        lambda url: "dodwarning.aspx" not in url.lower(),
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )
                except PlaywrightTimeoutError:
                    logger.info(
                        "The browser did not leave the warning page within 60 seconds after clicking OK."
                    )
                await page.wait_for_timeout(1000)
                logger.info("Current page after acknowledgement: %s", page.url)
                return True
        except PlaywrightTimeoutError:
            if "dodwarning.aspx" not in page.url.lower():
                logger.info(
                    "The click timed out, but the browser already left the warning page; treating it as acknowledged."
                )
                return True
            logger.warning(
                "An OK control was found but could not be clicked; trying another selector."
            )
    logger.warning("No visible OK control was found on this page.")
    logger.info("Page title: %s", await page.title())
    body_text = (await page.locator("body").inner_text())[:3000]
    logger.info("Page text for troubleshooting: %s", body_text.replace("\n", " | "))
    return False


async def open_rfq_page(
    page,
) -> bool:  # Open the RFQ page and get past the warning banner.
    logger.info("Opening official DIBBS Recent RFQ Dates page: %s", START_URL)
    response = await page.goto(START_URL, wait_until="domcontentloaded", timeout=60000)
    if response is not None:
        logger.info("Initial navigation returned HTTP %s.", response.status)
    await page.wait_for_load_state("domcontentloaded", timeout=15000)
    warning_attempts = 0
    while "dodwarning.aspx" in page.url.lower() and warning_attempts < 3:
        warning_attempts += 1
        logger.info("DIBBS redirected to its warning page; attempting to click OK.")
        if not await acknowledge_warning(page):
            logger.error(
                "Could not acknowledge the warning page automatically; leaving Chromium open for inspection."
            )
            await page.wait_for_timeout(30000)
            return False
        if "rfqdates.aspx" not in page.url.lower():
            logger.info("Returning to the RFQ page after acknowledgement.")
            await page.goto(START_URL, wait_until="domcontentloaded", timeout=60000)
    if "dodwarning.aspx" in page.url.lower():
        logger.warning("The browser is still on the warning page after clicking OK.")
        logger.info(
            "Leaving Chromium open for 30 seconds so the page can be inspected."
        )
        await page.wait_for_timeout(30000)
        return False
    logger.info("RFQ page is ready: %s", page.url)
    return True


async def collect_archive_urls(
    page,
) -> List[str]:  # Return every official ZIP link on the page.
    try:  # The RFQ page loads slowly, so wait for the links to exist.
        await page.wait_for_selector(
            'a[href*="/downloads/rfq/archive/" i]', state="attached", timeout=60000
        )
    except PlaywrightTimeoutError:
        logger.warning(
            "No archive link appeared within 60 seconds; continuing with what the page contains."
        )
    await page.wait_for_timeout(1500)
    links = await page.locator("a[href]").evaluate_all(
        "(anchors) => anchors.map(a => ({href: a.href, text: (a.innerText || a.textContent || '').trim()}))"
    )
    archive_urls = sorted(
        {item["href"] for item in links if is_allowed_archive_url(item["href"])}
    )
    logger.info("Found %d matching RFQ ZIP link(s).", len(archive_urls))
    if not archive_urls:
        logger.warning(
            "No matching archive links were found; logging links that mention ZIP or RFQ."
        )
        for item in links:
            if (
                "zip" in item["href"].lower()
                or "rfq" in item["href"].lower()
                or "zip" in item["text"].lower()
            ):
                logger.info("Possible link: text=%r url=%s", item["text"], item["href"])
        logger.info("Current page title: %s", await page.title())
        logger.info("Current page URL: %s", page.url)
    return archive_urls


def attach_page_listeners(
    page, stats: RunStats
) -> None:  # Log console, errors, network failures.
    def on_request_failed(request) -> None:  # Count and log failed browser requests.
        failure = request.failure or ""
        # A navigation that turns into a download is reported as ERR_ABORTED.
        # That is normal, so it is neither logged nor counted as a failure.
        if "ERR_ABORTED" in failure and request.url.lower().endswith(".zip"):
            return
        stats.failed_requests += 1
        logger.warning("REQUEST FAILED: %s | %s", request.url, failure)

    page.on(
        "console",
        lambda message: logger.info(
            "BROWSER CONSOLE [%s]: %s", message.type, message.text
        ),
    )
    page.on("pageerror", lambda error: logger.error("BROWSER PAGE ERROR: %s", error))
    page.on("requestfailed", on_request_failed)
    page.on(
        "response",
        lambda response: (
            logger.info("HTTP %s %s", response.status, response.url)
            if response.status >= 400
            else logger.debug("HTTP %s %s", response.status, response.url)
        ),
    )


# =====================================================================
# DOWNLOADING: DIRECT STREAMING (MAIN PATH)
# =====================================================================
# The DIBBS server (or the network path to it) drops large transfers partway,
# and a dropped browser download cannot be resumed. So the file is streamed
# directly, using the consent cookie the browser obtained:
#   * if the server honors HTTP Range requests, the file is fetched in short
#     ranged chunks, so a dropped connection costs seconds, never the file;
#   * if it does not, each attempt restarts from zero until one completes.
def open_url(
    url: str, cookie: str, user_agent: str, byte_range: Optional[Tuple[int, int]] = None
):
    headers = {
        "Cookie": cookie,  # Carries the consent the browser obtained.
        "User-Agent": user_agent,
        "Referer": START_URL,
        "Accept-Encoding": "identity",  # Keep byte counts exact.
    }
    if byte_range is not None:
        headers[
            "Range"
        ] = f"bytes={byte_range[0]}-{byte_range[1]}"  # Closed range, the most widely honored form.
    request = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(request, timeout=HTTP_READ_TIMEOUT_S)


def log_headers(
    name: str, response, label: str
) -> None:  # Record what the server says, for diagnosis.
    wanted = (
        "Accept-Ranges",
        "Content-Length",
        "Content-Range",
        "Content-Type",
        "Transfer-Encoding",
        "Server",
        "Connection",
        "Via",
    )
    parts = [
        f"{key}={response.headers.get(key)}"
        for key in wanted
        if response.headers.get(key) is not None
    ]
    logger.info(
        "%s: %s -> HTTP %s | %s", name, label, response.status, ", ".join(parts)
    )


def probe_range_sync(
    url: str, cookie: str, user_agent: str
) -> Tuple[str, Optional[int]]:
    """Ask for one byte to learn whether the server honors Range requests.

    Returns ("closed", total) when it does, ("none", total) when it sends the
    whole file anyway, ("banner", None) when the warning page came back, or
    ("error", None). The response is closed without downloading the body.
    """
    name = filename_from_url(url)
    try:
        response = open_url(url, cookie, user_agent, (0, 0))
    except urllib.error.HTTPError as exc:
        logger.warning("%s: probe got HTTP %s.", name, exc.code)
        return "error", None
    except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
        logger.warning("%s: probe could not connect: %s", name, exc)
        return "error", None
    with response:
        log_headers(name, response, "range probe")
        if response.headers.get("Content-Type", "").lower().startswith("text/html"):
            return "banner", None
        if response.status == 206:
            match = re.match(
                r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", "")
            )
            return ("closed", int(match.group(3))) if match else ("error", None)
        if response.status == 200:
            length = response.headers.get("Content-Length", "")
            return "none", (int(length) if length.isdigit() else None)
    return "error", None


def download_stream_sync(
    url: str,
    temp_path: Path,
    cookie: str,
    user_agent: str,
    byte_range: Optional[Tuple[int, int]],
    total: Optional[int],
) -> str:
    """One streaming request. With byte_range it appends that range to temp_path;
    without it, it writes the whole file from the start.

    Returns "ok", "dropped" (ended early; try again), "banner", "norange"
    (the server stopped honoring Range), or "failed" (HTTP error).
    """
    name = filename_from_url(url)
    try:
        response = open_url(url, cookie, user_agent, byte_range)
    except urllib.error.HTTPError as exc:
        logger.warning("%s: HTTP %s from server.", name, exc.code)
        return "failed"
    except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
        logger.warning("%s: could not connect: %s", name, exc)
        return "dropped"

    with response:
        if response.headers.get("Content-Type", "").lower().startswith("text/html"):
            return "banner"  # The warning page, not a ZIP.
        if byte_range is not None:
            if response.status != 206:
                logger.warning(
                    "%s: server stopped honoring Range requests (HTTP %s).",
                    name,
                    response.status,
                )
                return "norange"
            match = re.match(
                r"bytes (\d+)-(\d+)/(\d+|\*)", response.headers.get("Content-Range", "")
            )
            if not match or int(match.group(1)) != byte_range[0]:
                logger.warning(
                    "%s: unexpected Content-Range %r.",
                    name,
                    response.headers.get("Content-Range"),
                )
                return "failed"
            mode, written = "ab", byte_range[0]
            expected_end = int(match.group(2)) + 1  # File position after this chunk.
        else:
            if response.status != 200:
                logger.warning("%s: unexpected HTTP status %s.", name, response.status)
                return "failed"
            mode, written = "wb", 0
            expected_end = total  # May be None if the server sent no length.

        started = last_log = time.monotonic()
        start_bytes = written
        try:
            with temp_path.open(mode) as handle:
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    handle.write(chunk)
                    written += len(chunk)
                    now = time.monotonic()
                    if now - last_log >= PROGRESS_LOG_S:
                        last_log = now
                        rate = (
                            (written - start_bytes)
                            / 1048576
                            / max(now - started, 0.001)
                        )
                        of_total = f" of {total / 1048576:.0f} MB" if total else ""
                        logger.info(
                            "%s: %.0f MB%s (%.1f MB/s)",
                            name,
                            written / 1048576,
                            of_total,
                            rate,
                        )
        except (
            OSError,
            http.client.HTTPException,
        ) as exc:  # Includes read timeouts and resets.
            logger.warning(
                "%s: connection dropped at %.0f MB: %s", name, written / 1048576, exc
            )
            return "dropped"

    if (
        expected_end is not None and written < expected_end
    ):  # The server closed the connection early.
        logger.warning(
            "%s: connection ended early at %.0f of %.0f MB.",
            name,
            written / 1048576,
            expected_end / 1048576,
        )
        return "dropped"
    return "ok"


async def cookie_header(
    context, url: str
) -> str:  # Build a Cookie header from the browser's cookies.
    cookies = await context.cookies(url)
    return "; ".join(f"{cookie['name']}={cookie['value']}" for cookie in cookies)


def file_size(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


async def fetch_in_ranges(
    context, url: str, temp_path: Path, user_agent: str, total: int
) -> str:
    # Fetch the file in short ranged requests, continuing from the bytes already on disk.
    name = filename_from_url(url)
    size = file_size(temp_path)
    if size > total:  # A leftover that cannot belong to this file.
        temp_path.unlink(missing_ok=True)
        size = 0
    if size:
        logger.info(
            "%s: continuing from %.0f of %.0f MB already on disk.",
            name,
            size / 1048576,
            total / 1048576,
        )
    started = last_log = time.monotonic()
    start_size = size
    no_progress = 0  # Consecutive requests that added no bytes.
    while size < total:
        end = min(size + RANGE_CHUNK_BYTES, total) - 1
        cookie = await cookie_header(context, url)  # Refresh in case cookies changed.
        result = await asyncio.to_thread(
            download_stream_sync, url, temp_path, cookie, user_agent, (size, end), total
        )
        if result in ("banner", "norange"):
            return (
                "banner"
                if result == "banner"
                else await fetch_whole_file(context, url, temp_path, user_agent, total)
            )
        new_size = file_size(temp_path)
        no_progress = 0 if new_size > size else no_progress + 1
        size = new_size
        if no_progress >= MAX_NO_PROGRESS_ATTEMPTS:
            logger.warning(
                "%s: no progress after %d requests in a row; giving up on direct download.",
                name,
                no_progress,
            )
            return "failed"
        if (
            result != "ok"
        ):  # A short pause after a drop or error, none between healthy chunks.
            await asyncio.sleep(min(3 * (no_progress + 1), 30))
        now = time.monotonic()
        if now - last_log >= PROGRESS_LOG_S:
            last_log = now
            rate = (size - start_size) / 1048576 / max(now - started, 0.001)
            logger.info(
                "%s: %.0f MB of %.0f MB (%.1f MB/s)",
                name,
                size / 1048576,
                total / 1048576,
                rate,
            )
    return "complete"


async def fetch_whole_file(
    context, url: str, temp_path: Path, user_agent: str, total: Optional[int]
) -> str:
    # The server cannot resume, so restart from zero until one attempt gets all the way through.
    name = filename_from_url(url)
    for attempt in range(1, MAX_FULL_ATTEMPTS + 1):
        temp_path.unlink(missing_ok=True)
        cookie = await cookie_header(context, url)
        logger.info(
            "%s: downloading from the start (attempt %d/%d).",
            name,
            attempt,
            MAX_FULL_ATTEMPTS,
        )
        began = time.monotonic()
        result = await asyncio.to_thread(
            download_stream_sync, url, temp_path, cookie, user_agent, None, total
        )
        if result == "ok":
            return "complete"
        if result in ("banner", "failed"):
            return result
        logger.warning(
            "%s: attempt %d/%d dropped after %.0f seconds.",
            name,
            attempt,
            MAX_FULL_ATTEMPTS,
            time.monotonic() - began,
        )
        await asyncio.sleep(FULL_RETRY_DELAY_S)
    temp_path.unlink(missing_ok=True)
    return "exhausted"


async def fetch_resumable(
    context, archive_url: str, temp_path: Path, user_agent: str
) -> str:
    # Pick the best strategy for this server. Returns "complete", "banner", "failed", or "exhausted".
    name = filename_from_url(archive_url)
    cookie = await cookie_header(context, archive_url)
    mode, total = await asyncio.to_thread(
        probe_range_sync, archive_url, cookie, user_agent
    )
    if mode in ("banner", "error"):
        return "banner" if mode == "banner" else "failed"
    if mode == "closed" and total:
        logger.info(
            "%s: server supports Range requests; downloading in %d MB chunks.",
            name,
            RANGE_CHUNK_BYTES // 1048576,
        )
        return await fetch_in_ranges(context, archive_url, temp_path, user_agent, total)
    logger.warning(
        "%s: server does not support Range requests, so a dropped connection means starting over.",
        name,
    )
    return await fetch_whole_file(context, archive_url, temp_path, user_agent, total)


async def acquire_consent(page, archive_url: str) -> bool:
    # Pass the warning banner in the browser, then cancel the download it starts.
    # The consent cookie it leaves behind is what the streaming downloader uses.
    loop = asyncio.get_running_loop()
    download_future = loop.create_future()

    def on_download(download) -> None:
        if not download_future.done():
            download_future.set_result(download)

    page.on("download", on_download)
    try:
        try:
            await page.goto(
                archive_url,
                referer=START_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )
            page_loaded = True
        except PlaywrightError as exc:  # Chromium reports a starting download as a navigation error.
            if "download is starting" not in str(exc).lower():
                raise
            page_loaded = False
        if page_loaded:  # Probably the warning banner.
            button = page.locator("#butAgree")
            if await button.count() == 0:
                logger.error(
                    "The browser got a page instead of the banner: %s | title: %s",
                    page.url,
                    await page.title(),
                )
                return False
            logger.info("Warning banner shown at %s; clicking OK.", page.url)
            await button.first.click(timeout=5000, no_wait_after=True)
        download = await asyncio.wait_for(
            download_future, timeout=BROWSER_DOWNLOAD_TIMEOUT_S
        )
        await download.cancel()  # The consent is stored; the streaming path downloads the file.
        try:
            await download.delete()
        except PlaywrightError:
            pass
        logger.info("Warning banner passed; switching to resumable download.")
        return True
    except asyncio.TimeoutError:
        logger.error(
            "The browser never started a download while passing the banner for %s.",
            archive_url,
        )
        return False
    finally:
        page.remove_listener("download", on_download)


# =====================================================================
# DOWNLOADING: BROWSER FALLBACK
# =====================================================================
class DownloadStalled(
    Exception
):  # Raised when a download stops progressing or hits the hard cap.
    pass


def staged_bytes() -> int:  # Total size of everything Chromium has staged so far.
    total = 0
    try:
        for item in BROWSER_DOWNLOAD_DIR.rglob("*"):
            try:
                if item.is_file():
                    total += item.stat().st_size
            except OSError:
                pass  # The file may have been renamed or removed mid-scan.
    except OSError:
        pass
    return total


async def save_with_watchdog(download, temp_path: Path, label: str) -> None:
    # Save the download, giving up only if it stalls or exceeds the hard cap.
    save_task = asyncio.ensure_future(download.save_as(temp_path))
    started = time.monotonic()
    baseline = staged_bytes()
    last_bytes = baseline
    last_growth = started
    last_log = started
    saw_growth = False  # If bytes never visibly grow, progress is unknowable, so only the hard cap applies.
    try:
        while not save_task.done():
            await asyncio.wait({save_task}, timeout=PROGRESS_POLL_S)
            if save_task.done():
                break
            now = time.monotonic()
            current = staged_bytes()
            if current > last_bytes:
                saw_growth = True
                last_growth = now
            last_bytes = current
            if now - last_log >= PROGRESS_LOG_S:
                last_log = now
                short = label.rsplit("/", 1)[-1]
                if saw_growth:
                    mb = (current - baseline) / 1048576
                    logger.info(
                        "%s: %.0f MB so far (%.1f MB/s average)",
                        short,
                        mb,
                        mb / (now - started),
                    )
                else:
                    logger.info("%s: still downloading (progress not visible)", short)
            if now - started > BROWSER_SAVE_MAX_S:
                raise DownloadStalled(f"exceeded the {BROWSER_SAVE_MAX_S}s hard cap")
            if saw_growth and now - last_growth > STALL_TIMEOUT_S:
                raise DownloadStalled(f"no progress for {STALL_TIMEOUT_S}s")
        await save_task  # Re-raise any error from save_as itself.
    except BaseException:
        if not save_task.done():
            save_task.cancel()
            try:
                await save_task
            except BaseException:
                pass
        raise


async def fetch_via_browser(page, archive_url: str, temp_path: Path) -> bool:
    loop = asyncio.get_running_loop()
    download_future = (
        loop.create_future()
    )  # Resolved when the browser starts a download.

    def on_download(download) -> None:
        if not download_future.done():
            download_future.set_result(download)

    page.on("download", on_download)  # Listen before navigating so no event is missed.
    try:
        try:  # Navigate like a person clicking the link on the RFQ page.
            await page.goto(
                archive_url,
                referer=START_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )
            page_loaded = True  # A normal page loaded, so no download started yet.
        except PlaywrightError as exc:  # Chromium reports a starting download as a navigation error.
            if "download is starting" not in str(exc).lower():
                raise
            page_loaded = False
        if page_loaded:  # Probably the warning banner.
            button = page.locator("#butAgree")
            if await button.count() == 0:
                logger.error(
                    "The browser got a page instead of a ZIP: %s | title: %s",
                    page.url,
                    await page.title(),
                )
                return False
            form_action = await page.locator("form").first.get_attribute("action")
            logger.info(
                "Warning banner shown at %s (form action: %s); clicking OK.",
                page.url,
                form_action,
            )
            await button.first.click(timeout=5000, no_wait_after=True)

        try:  # Wait for the download to START.
            download = await asyncio.wait_for(
                download_future, timeout=BROWSER_DOWNLOAD_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            logger.error(
                "The browser never started a download for %s (page: %s | title: %s)",
                archive_url,
                page.url,
                await page.title(),
            )
            return False

        try:  # Wait for the download to FINISH; slow is fine, stalled is not.
            await save_with_watchdog(download, temp_path, archive_url)
        except DownloadStalled as exc:
            logger.warning(
                "Download gave up for %s: %s; canceling it.", archive_url, exc
            )
            try:
                await download.cancel()  # Drop the stalled transfer.
            except PlaywrightError:
                pass
            temp_path.unlink(missing_ok=True)
            return False
        except PlaywrightError as exc:
            try:  # Ask the browser why the download ended.
                reason = await asyncio.wait_for(download.failure(), timeout=5)
            except (asyncio.TimeoutError, PlaywrightError):
                reason = "unknown"
            logger.warning(
                "Download did not finish for %s: %s | failure=%s",
                archive_url,
                exc,
                reason,
            )
            temp_path.unlink(missing_ok=True)
            return False
        try:
            await download.delete()  # Remove Chromium's staged copy so a 2 GB file is not stored twice.
        except PlaywrightError:
            pass
        return True
    finally:
        page.remove_listener("download", on_download)


# =====================================================================
# DOWNLOADING: PER-ARCHIVE WORKFLOW
# =====================================================================
async def download_archive(
    context, page, archive_url: str, stats: RunStats, user_agent: str
) -> None:  # Download one archive and save it under the filename from its URL.
    logger.info("Processing archive URL: %s", archive_url)
    filename = filename_from_url(archive_url)
    zip_path = ZIP_DIR / filename
    assert zip_path.parent == ZIP_DIR, f"Unsafe ZIP filename: {filename}"
    temp_path = zip_path.with_name(
        zip_path.name + ".part"
    )  # Partial file; kept between runs so a rerun can resume.
    logger.info("Local filename from URL: %s", filename)
    if zip_path.is_file() and zipfile.is_zipfile(zip_path):
        logger.info("%s is already downloaded; skipping.", filename)
        stats.skipped += 1
        return

    # 1) Direct streaming download (ranged chunks if the server allows, otherwise whole-file retries).
    result = await fetch_resumable(context, archive_url, temp_path, user_agent)
    if (
        result == "banner"
    ):  # No consent cookie yet: pass the banner in the browser, then retry.
        logger.info(
            "The warning banner blocked the direct download; passing it in the browser first."
        )
        if await acquire_consent(page, archive_url):
            result = await fetch_resumable(context, archive_url, temp_path, user_agent)
        else:
            result = "failed"
    if (
        result == "exhausted"
    ):  # The browser would be dropped the same way, so do not fall back to it.
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"The connection dropped on all {MAX_FULL_ATTEMPTS} attempts for {archive_url}; try again later."
        )
    saved = False
    if result == "complete":
        if zipfile.is_zipfile(temp_path):
            saved = True
        else:
            logger.warning(
                "The streamed file for %s is not a valid ZIP; discarding it.", filename
            )
            temp_path.unlink(missing_ok=True)

    # 2) Last resort: the plain browser download, with a stall watchdog and retries.
    if not saved:
        logger.info(
            "Direct download did not work for %s; falling back to the browser download.",
            filename,
        )
        temp_path.unlink(missing_ok=True)
        for attempt in range(1, MAX_BROWSER_ATTEMPTS + 1):
            try:
                saved = await fetch_via_browser(page, archive_url, temp_path)
            except PlaywrightError as exc:
                logger.warning(
                    "Browser attempt raised an error for %s: %s", archive_url, exc
                )
                saved = False
            if saved:
                break
            logger.warning(
                "Browser attempt %d/%d failed for %s",
                attempt,
                MAX_BROWSER_ATTEMPTS,
                archive_url,
            )
            if attempt < MAX_BROWSER_ATTEMPTS:
                await asyncio.sleep(5 * attempt)  # Back off before retrying.

    if not saved or not zipfile.is_zipfile(temp_path):
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"No valid ZIP could be saved for {archive_url}")
    size = temp_path.stat().st_size
    temp_path.replace(
        zip_path
    )  # Move the finished file onto its final name in one step.
    stats.downloaded += 1
    logger.info("Saved %s (%d bytes)", zip_path, size)


async def run_downloads(
    context, page, archive_urls: List[str], stats: RunStats, user_agent: str
) -> None:
    for archive_url in archive_urls:
        try:  # Keep one failed archive from stopping the rest.
            await download_archive(context, page, archive_url, stats, user_agent)
        except Exception as exc:
            stats.failed += 1
            logger.exception("Failed to process archive %s: %s", archive_url, exc)


def log_summary(stats: RunStats) -> None:
    logger.info("========== RUN SUMMARY ==========")
    logger.info("New ZIP downloads: %d", stats.downloaded)
    logger.info("Already downloaded (skipped): %d", stats.skipped)
    logger.info("Failures: %d", stats.failed)
    logger.info("Failed browser requests: %d", stats.failed_requests)
    logger.info("ZIP folder: %s", ZIP_DIR.resolve())


# =====================================================================
# ENTRY POINT
# =====================================================================
async def main() -> None:
    ZIP_DIR.mkdir(parents=True, exist_ok=True)
    BROWSER_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stats = RunStats()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=False,  # Visible Chromium.
            downloads_path=str(
                BROWSER_DOWNLOAD_DIR
            ),  # Stage browser downloads here so progress can be watched.
        )
        context = await browser.new_context(
            accept_downloads=True, ignore_https_errors=False
        )
        page = await context.new_page()
        page.set_default_timeout(TIMEOUT_MS)
        attach_page_listeners(page, stats)
        try:
            if not await open_rfq_page(page):
                return
            archive_urls = await collect_archive_urls(page)
            user_agent = await page.evaluate(
                "navigator.userAgent"
            )  # Make streamed requests look like the browser's.
            await run_downloads(context, page, archive_urls, stats, user_agent)
            log_summary(stats)
            logger.info("Chromium will remain open for 30 seconds before closing.")
            await page.wait_for_timeout(30000)
        except Exception as exc:
            logger.exception("The DIBBS downloader stopped unexpectedly: %s", exc)
            logger.info(
                "Chromium will remain open for 30 seconds for inspection if possible."
            )
            try:
                await page.wait_for_timeout(30000)
            except Exception:
                pass
        finally:
            try:
                await context.close()
            finally:
                await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
