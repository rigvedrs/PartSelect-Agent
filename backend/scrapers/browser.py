"""Shared Chrome WebDriver setup for PartSelect scraping."""
from __future__ import annotations

import time
from typing import Callable

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

_STEALTH_JS = "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)


def build_chrome(headless: bool = True, window_size: str = "1400,1000") -> webdriver.Chrome:
    import os
    opts = Options()
    chrome_bin = os.getenv("CHROME_BIN")
    if chrome_bin:
        opts.binary_location = chrome_bin
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument(f"--window-size={window_size}")
    opts.add_argument("--lang=en-US,en")
    opts.add_argument(f"--user-agent={_DEFAULT_UA}")
    driver_path = os.getenv("CHROMEDRIVER_PATH")
    if driver_path:
        service = Service(driver_path)
    else:
        service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": _STEALTH_JS},
        )
    except Exception:
        pass
    return driver


def wait_for_body(driver: webdriver.Chrome, timeout: float = 20) -> None:
    WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))


def brief_pause(seconds: float = 0.25) -> None:
    time.sleep(seconds)


def try_click(driver: webdriver.Chrome, *locators: tuple[str, str]) -> bool:
    for by, selector in locators:
        try:
            elements = driver.find_elements(by, selector)
            if not elements:
                continue
            el = elements[0]
            try:
                el.click()
            except Exception:
                driver.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            continue
    return False


def dismiss_overlays(driver: webdriver.Chrome, max_iframes: int = 4) -> None:
    if try_click(
        driver,
        (By.XPATH, "//button[normalize-space()='Decline']"),
        (By.XPATH, "//a[normalize-space()='Decline']"),
        (By.XPATH, "//button[contains(.,'Decline all')]"),
        (By.XPATH, "//button[contains(.,'No thanks')]"),
        (
            By.CSS_SELECTOR,
            "button[aria-label='Close'], .mfp-close, .modal .close, "
            ".ps-modal .close, .optanon-alert-box-close",
        ),
    ):
        return
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except Exception:
        pass
    try:
        for frame in driver.find_elements(By.TAG_NAME, "iframe")[:max_iframes]:
            try:
                driver.switch_to.frame(frame)
                if try_click(
                    driver,
                    (By.XPATH, "//button[normalize-space()='Decline']"),
                    (By.XPATH, "//a[normalize-space()='Decline']"),
                    (By.CSS_SELECTOR, "button[aria-label='Close'], .mfp-close, .modal .close"),
                ):
                    driver.switch_to.default_content()
                    return
            finally:
                driver.switch_to.default_content()
    except Exception:
        pass


def navigate(driver: webdriver.Chrome, url: str, on_ready: Callable | None = None) -> None:
    driver.get(url)
    dismiss_overlays(driver)
    wait_for_body(driver)
    if on_ready:
        on_ready(driver)
