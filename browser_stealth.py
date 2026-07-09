"""
Browser Stealth Module -- Launches a hardened Playwright Chromium browser.

Patches WebDriver leaks, sets realistic fingerprints, and optionally
routes through a proxy.
"""

import random
import logging
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth import Stealth

from config import (
    BROWSER_ARGS,
    HEADLESS,
    PROXY,
    VIEWPORT_POOL,
    USER_AGENT_POOL,
)
from anti_detect import random_viewport, random_user_agent

logger = logging.getLogger(__name__)


async def launch_stealth_browser(
    headless: bool = None,
) -> tuple:
    """
    Launch a stealth-hardened Chromium browser.

    Returns:
        (playwright_instance, browser, context, page)
    """
    if headless is None:
        headless = HEADLESS

    pw = await async_playwright().start()

    # -- Browser launch args --
    launch_args = list(BROWSER_ARGS)

    # -- Proxy config --
    proxy_config = None
    if PROXY:
        proxy_config = {"server": PROXY}
        logger.info(f"[NET] Using proxy: {PROXY}")

    browser = await pw.chromium.launch(
        headless=headless,
        args=launch_args,
        proxy=proxy_config,
    )

    # -- Random fingerprint --
    viewport = random_viewport(VIEWPORT_POOL)
    user_agent = random_user_agent(USER_AGENT_POOL)

    logger.info(f"[PC] Viewport: {viewport['width']}x{viewport['height']}")
    logger.info(f"[SPY] User-Agent: {user_agent[:60]}...")

    # -- Browser context with realistic settings --
    context = await browser.new_context(
        viewport=viewport,
        user_agent=user_agent,
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        geolocation={"latitude": 17.385044, "longitude": 78.486671},  # Hyderabad center
        permissions=["geolocation"],
        color_scheme=random.choice(["light", "dark", "no-preference"]),
        java_script_enabled=True,
        has_touch=False,
        is_mobile=False,
        device_scale_factor=random.choice([1, 1.25, 1.5, 2]),
    )

    # -- Suppress common popups --
    await context.add_cookies([
        {
            "name": "CONSENT",
            "value": "YES+cb.20231120-04-p0.en+FX+410",
            "domain": ".google.com",
            "path": "/",
        },
        {
            "name": "SOCS",
            "value": "CAISHAgCEhJnd3NfMjAyMzExMjAtMF9SQzIaAmVuIAEaBgiA0JiqBg",
            "domain": ".google.com",
            "path": "/",
        },
    ])

    page = await context.new_page()

    # -- Intercept and block telemetry/tracking to prevent detection and speed up load --
    async def route_interceptor(route):
        url = route.request.url.lower()
        block_patterns = [
            "google-analytics", "analytics.js", "gtm.js", "googletagmanager",
            "/log?", "gen_204", "play.google.com/log", "collect?", "telemetry",
            "stats.g.doubleclick.net", "adsbygoogle", "adsense"
        ]
        if any(pat in url for pat in block_patterns):
            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", route_interceptor)

    # -- Apply playwright-stealth patches --
    stealth = Stealth(
        navigator_languages_override=("en-IN", "en-US"),
        navigator_platform_override="Win32",
    )
    await stealth.apply_stealth_async(page)

    # -- Extra JS patches for deeper evasion --
    await page.add_init_script("""
        // Override navigator.webdriver
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });

        // Override navigator.plugins to look real
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });

        // Override navigator.languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-IN', 'en-US', 'en'],
        });

        // Canvas Fingerprinting Defeat
        const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
        CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
            const imgData = originalGetImageData.apply(this, arguments);
            if (imgData.data.length > 0) {
                // Add extremely subtle noise to the last pixel to throw off signature hashes
                imgData.data[imgData.data.length - 1] = (imgData.data[imgData.data.length - 1] + 1) % 256;
            }
            return imgData;
        };

        // WebGL / GPU Spoofing
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            // UNMASKED_RENDERER_WEBGL
            if (parameter === 37446) {
                return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)';
            }
            // UNMASKED_VENDOR_WEBGL
            if (parameter === 37445) {
                return 'Google Inc. (NVIDIA)';
            }
            return getParameter.apply(this, arguments);
        };
        if (window.WebGL2RenderingContext) {
            const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
            WebGL2RenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37446) {
                    return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)';
                }
                if (parameter === 37445) {
                    return 'Google Inc. (NVIDIA)';
                }
                return getParameter2.apply(this, arguments);
            };
        }

        // Hardware details
        Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
        Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

        // UserAgentData spoofer
        if (navigator.userAgentData) {
            Object.defineProperty(navigator.userAgentData, 'platform', { get: () => 'Windows' });
        }

        // Chrome runtime mock
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {},
        };

        // Permissions query override
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);
    """)

    logger.info("[OK] Stealth browser launched successfully")
    return pw, browser, context, page


async def close_browser(pw, browser) -> None:
    """Gracefully close browser and Playwright."""
    try:
        await browser.close()
    except Exception:
        pass
    try:
        await pw.stop()
    except Exception:
        pass
    logger.info("[LOCK] Browser closed")
