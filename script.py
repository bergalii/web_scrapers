import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
)
from selenium.webdriver.common.action_chains import ActionChains
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests
import os
import json
import time

# Default variables
CHROME_OPTIONS = uc.ChromeOptions()
CHROME_OPTIONS.headless = False
CHROME_OPTIONS.add_argument("--disable-search-engine-choice-screen")
MAIN_PAGE_URL = "https://www.reddit.com/r/laundry/"


class RedditCrawler:
    def __init__(self):
        self.driver = uc.Chrome(use_subprocess=True, options=CHROME_OPTIONS)
        self.timeout = 20
        self.wait = WebDriverWait(self.driver, self.timeout)
        self.loop = True
        self.folder_path = "./images"  # Folder to save the images
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)
        self.session = requests.Session()
        self.mount_retry_adapter()

    def mount_retry_adapter(self):
        retries = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=[
                "HEAD",
                "GET",
                "OPTIONS",
            ],  # Change from method_whitelist to allowed_methods
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def start(self):
        try:
            self.driver.get(MAIN_PAGE_URL)
            while True:
                self.process_visible_images()
                if not self.scroll_down():
                    break
        finally:
            self.terminate()

    def process_visible_images(self):
        image_elements = self.wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img.preview-img"))
        )
        for img in image_elements:
            if self.is_valid_image(img):
                self.click_and_download_image(img)

    def is_valid_image(self, img):
        src = img.get_attribute("src")
        return not src.startswith("https://external-preview.redd.it")

    def click_and_download_image(self, img):
        try:
            # Scroll the image into view
            self.driver.execute_script("arguments[0].scrollIntoView(true);", img)
            time.sleep(0.5)  # Short pause to let any animations complete

            # Try to click the image
            try:
                img.click()
                time.sleep(0.5)
            except ElementClickInterceptedException:
                # If direct click fails, try using JavaScript
                self.driver.execute_script("arguments[0].click();", img)
            time.sleep(1)
            lightbox_img = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "img.min-h-full"))
            )
            time.sleep(1)
            image_url = lightbox_img.get_attribute("src")
            self.download_image(image_url)
            self.close_lightbox()
        except Exception as e:
            print(f"Error processing image: {e}")

    def download_image(self, image_url):
        filename = os.path.basename(image_url)
        image_path = os.path.join(self.folder_path, filename)
        if not os.path.exists(image_path):
            try:
                response = self.session.get(image_url, timeout=10)
                if response.status_code == 200:
                    with open(image_path, "wb") as image_file:
                        image_file.write(response.content)
                    print(f"Downloaded: {filename}")
                else:
                    print(f"Failed to download: {filename}")
            except requests.RequestException as e:
                print(f"Error downloading {filename}: {e}")
        else:
            print(f"Image already exists: {filename}, skipping.")

    def close_lightbox(self):
        try:
            close_button = self.wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button[aria-label='Close lightbox']")
                )
            )
            close_button.click()
        except Exception as e:
            print(f"Error closing lightbox: {e}")
            # If we can't close normally, try to click outside the lightbox
            try:
                ActionChains(self.driver).move_by_offset(0, 0).click().perform()
            except:
                print("Failed to close lightbox by clicking outside")

    def scroll_down(self):
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  # Wait for page to load
        new_height = self.driver.execute_script("return document.body.scrollHeight")
        return new_height > last_height

    def terminate(self):
        print("Terminating the program.")
        self.driver.quit()


def main():
    print("------- Welcome --------")
    crawler = RedditCrawler()
    crawler.start()


if __name__ == "__main__":
    main()
