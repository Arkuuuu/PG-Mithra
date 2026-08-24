"""
Anti-Detection Module -- Random helper functions for stealth.

All randomness uses Python's stdlib `random` module.
These functions simulate human-like behaviour to avoid bot detection.
"""

import random
import asyncio
import math
import logging

logger = logging.getLogger(__name__)


# ===============================================
# 1. Random Delay
# ===============================================
async def random_delay(min_s: float, max_s: float) -> float:
    """Sleep for a random duration between min_s and max_s seconds."""
    duration = random.uniform(min_s, max_s)
    logger.debug(f"  [WAIT] Random delay: {duration:.2f}s")
    await asyncio.sleep(duration)
    return duration


# ===============================================
# 2. Random Mouse Move (Bezier-like path)
# ===============================================
async def random_mouse_move(page) -> None:
    """
    Move mouse to a random viewport coordinate along a curved path.
    Uses quadratic Bezier interpolation for natural movement.
    """
    viewport = page.viewport_size
    if not viewport:
        return

    # Random target within the visible area (avoid edges)
    target_x = random.randint(100, viewport["width"] - 100)
    target_y = random.randint(100, viewport["height"] - 100)

    # Get current mouse position (approximate -- start from center-ish)
    start_x = random.randint(
        viewport["width"] // 4, viewport["width"] * 3 // 4
    )
    start_y = random.randint(
        viewport["height"] // 4, viewport["height"] * 3 // 4
    )

    # Bezier control point -- offset for curvature
    ctrl_x = (start_x + target_x) // 2 + random.randint(-150, 150)
    ctrl_y = (start_y + target_y) // 2 + random.randint(-150, 150)

    # Number of steps for the curve
    steps = random.randint(12, 25)

    for i in range(steps + 1):
        t = i / steps
        # Quadratic Bezier: B(t) = (1-t)^2P0 + 2(1-t)tP1 + t^2P2
        x = (1 - t) ** 2 * start_x + 2 * (1 - t) * t * ctrl_x + t ** 2 * target_x
        y = (1 - t) ** 2 * start_y + 2 * (1 - t) * t * ctrl_y + t ** 2 * target_y
        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.008, 0.03))

    logger.debug(f"  [MOUSE] Mouse moved to ({target_x}, {target_y})")


# ===============================================
# 3. Random Scroll (for results panel)
# ===============================================
async def random_scroll(page, panel_selector: str, step_min: int = 300, step_max: int = 700) -> None:
    """
    Scroll a specific panel (e.g. the Maps results feed) by a random pixel amount.
    """
    scroll_amount = random.randint(step_min, step_max)
    try:
        await page.evaluate(
            f"""
            (selector) => {{
                const panel = document.querySelector(selector);
                if (panel) {{
                    panel.scrollTop += {scroll_amount};
                }}
            }}
            """,
            panel_selector,
        )
        logger.debug(f"  [SCROLL] Scrolled panel by {scroll_amount}px")
    except Exception:
        # Fallback: scroll with mouse wheel
        await page.mouse.wheel(0, scroll_amount)
        logger.debug(f"  [SCROLL] Fallback wheel scroll by {scroll_amount}px")

    await asyncio.sleep(random.uniform(0.5, 1.5))


# ===============================================
# 4. Random Typing (human-like keystroke timing)
# ===============================================
async def random_typing(page, selector: str, text: str, delay_range: tuple = (0.04, 0.18)) -> None:
    """
    Type text character-by-character with random inter-key delays.
    Occasionally introduces typos, correction backspaces, and thinking pauses.
    """
    await page.click(selector)
    await random_delay(0.3, 0.7)

    # Clear existing text
    await page.fill(selector, "")
    await random_delay(0.2, 0.5)

    keyboard = page.keyboard
    nearby_chars = {
        'a': 'qwsz', 'b': 'ghvn', 'c': 'xdfv', 'd': 'ersfxc', 'e': 'wsdr',
        'f': 'rtgvcd', 'g': 'tyhbvf', 'h': 'yujnbg', 'i': 'ujko', 'j': 'uikmnh',
        'k': 'ijlm', 'l': 'okp', 'm': 'njk', 'n': 'bhjm', 'o': 'iklp', 'p': 'ol',
        'q': 'wa', 'r': 'edf', 's': 'wazxde', 't': 'rfgy', 'u': 'yhji',
        'v': 'cfgb', 'w': 'qase', 'x': 'zsdc', 'y': 'tghu', 'z': 'asx'
    }

    for i, char in enumerate(text):
        # 5% chance of making a typo if it's an alphabetical char
        if char.lower() in nearby_chars and random.random() < 0.05:
            typo_char = random.choice(nearby_chars[char.lower()])
            # Type incorrect character
            await keyboard.type(typo_char)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
            # Backspace it
            await keyboard.press("Backspace")
            await asyncio.sleep(random.uniform(0.15, 0.4))
            
        await keyboard.type(char)
        delay = random.uniform(*delay_range)

        # Occasional longer pause (hesitation) - 10% chance
        if random.random() < 0.10:
            delay += random.uniform(0.3, 0.8)

        await asyncio.sleep(delay)

    logger.debug(f"  [KEY] Typed: '{text}'")


# ===============================================
# 5. Random Viewport
# ===============================================
def random_viewport(viewport_pool: list) -> dict:
    """Return a random realistic viewport size from the pool."""
    vp = random.choice(viewport_pool)
    # Add slight jitter so it's not an exact known resolution
    return {
        "width": vp["width"] + random.randint(-20, 20),
        "height": vp["height"] + random.randint(-10, 10),
    }


# ===============================================
# 6. Random User-Agent
# ===============================================
def random_user_agent(ua_pool: list) -> str:
    """Return a random modern Chrome user-agent string."""
    return random.choice(ua_pool)


# ===============================================
# 7. Random Pause Between Listings
# ===============================================
async def random_pause_between_listings(min_s: float = 2.0, max_s: float = 5.0) -> None:
    """Wait a random duration to simulate a human reading a listing."""
    duration = random.uniform(min_s, max_s)
    logger.debug(f"  [READ] Reading pause: {duration:.2f}s")
    await asyncio.sleep(duration)


# ===============================================
# 8. Jitter Click (click with random offset)
# ===============================================
async def jitter_click(page, selector: str = None, element=None) -> None:
    """
    Click an element with a slight random offset from its center.
    Accepts either a CSS selector or a Playwright element handle.
    """
    try:
        if element:
            box = await element.bounding_box()
        elif selector:
            el = page.locator(selector).first
            box = await el.bounding_box()
        else:
            return

        if box:
            # Random offset within the element bounds (not too close to edges)
            offset_x = random.uniform(box["width"] * 0.2, box["width"] * 0.8)
            offset_y = random.uniform(box["height"] * 0.2, box["height"] * 0.8)
            click_x = box["x"] + offset_x
            click_y = box["y"] + offset_y

            await page.mouse.click(click_x, click_y)
            logger.debug(f"  [HIT] Jitter click at ({click_x:.0f}, {click_y:.0f})")
        else:
            # Fallback to standard click
            if element:
                await element.click()
            elif selector:
                await page.click(selector)
    except Exception as e:
        logger.debug(f"  [!] Jitter click fallback: {e}")
        if selector:
            try:
                await page.click(selector)
            except Exception:
                pass


# ===============================================
# 9. Random Page Interaction (fake browsing)
# ===============================================
async def random_page_interaction(page) -> None:
    """
    Perform a random 'idle' interaction on the page to look human.
    Randomly picks one: mouse move, small scroll, or hover on map.
    """
    action = random.choice(["mouse_move", "map_hover", "small_scroll", "nothing"])

    if action == "mouse_move":
        await random_mouse_move(page)

    elif action == "map_hover":
        # Hover over the map area
        viewport = page.viewport_size
        if viewport:
            map_x = random.randint(viewport["width"] // 2, viewport["width"] - 50)
            map_y = random.randint(100, viewport["height"] - 50)
            await page.mouse.move(map_x, map_y)
            await random_delay(0.5, 1.5)
            logger.debug(f"  [MAP] Hovered over map area")

    elif action == "small_scroll":
        scroll_amount = random.randint(50, 200)
        direction = random.choice([1, -1])
        await page.mouse.wheel(0, scroll_amount * direction)
        await random_delay(0.3, 0.8)
        logger.debug(f"  [SCROLL] Idle scroll: {scroll_amount * direction}px")

    else:
        # Do nothing -- sometimes humans just stare at the screen
        await random_delay(0.5, 2.0)
        logger.debug(f"  [IDLE] Idle pause (doing nothing)")
