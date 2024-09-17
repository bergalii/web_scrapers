import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    ElementClickInterceptedException,
)
from selenium.webdriver.common.action_chains import ActionChains
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests
import os
import time
import re
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

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
        self.folder_path = "./images"
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)
        self.session = requests.Session()
        self.mount_retry_adapter()
        self.processed_images = set()

    def mount_retry_adapter(self):
        retries = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def start(self):
        try:
            self.driver.get(MAIN_PAGE_URL)
            while True:
                try:
                    self.process_visible_images()
                    self.process_gallery_carousels()
                    if not self.scroll_down():
                        break
                except Exception as e:
                    logging.error(f"Error while processing images or scrolling: {e}")
        except Exception as e:
            logging.error(f"Failed to start the crawler: {e}")
        finally:
            self.terminate()

    def process_visible_images(self):
        try:
            zoomable_img_elements = self.wait.until(
                EC.presence_of_all_elements_located((By.TAG_NAME, "zoomable-img"))
            )
            logging.info(
                f"{len(zoomable_img_elements)} images found in the current page, starting the download process."
            )
            for zoomable_img_element in zoomable_img_elements:
                try:
                    img_element = zoomable_img_element.find_element(By.TAG_NAME, "img")
                    image_src = img_element.get_attribute("src")
                    # Skip already processed images
                    if image_src in self.processed_images:
                        continue
                    # Add image src to processed set
                    self.processed_images.add(image_src)
                    if self.is_valid_image(image_src):
                        self.download_image(image_src)
                except Exception as e:
                    logging.error(f"Error processing image: {e}")
        except TimeoutException:
            logging.warning("No images found, continuing to scroll...")

    def process_gallery_carousels(self):
        try:
            carousel_elements = self.wait.until(
                EC.presence_of_all_elements_located((By.TAG_NAME, "gallery-carousel"))
            )
            logging.info(
                f"{len(carousel_elements)} gallery carousels found in the current page, processing images."
            )
            for carousel in carousel_elements:
                try:
                    img_elements = carousel.find_elements(By.TAG_NAME, "img")
                    for img in img_elements:
                        image_src = img.get_attribute("src")
                        if image_src and image_src not in self.processed_images:
                            self.processed_images.add(image_src)
                            image_id = self.extract_image_id(image_src)
                            print(image_id)
                            if image_id:
                                full_res_url = f"https://i.redd.it/{image_id}"
                                self.download_image(full_res_url)
                except Exception as e:
                    logging.error(f"Error processing carousel image: {e}")
        except TimeoutException:
            logging.warning("No gallery carousels found, continuing to scroll...")

    def extract_image_id(self, url):
        match = re.search(r"v0-([^?]+)", url)
        return match.group(1) if match else None

    def is_valid_image(self, src):
        try:
            return not src.startswith("https://external-preview.redd.it")
        except Exception as e:
            logging.error(f"Error checking image validity: {e}")
            return False

    def download_image(self, image_url):
        filename = os.path.basename(image_url)
        image_path = os.path.join(self.folder_path, filename)

        if not os.path.exists(image_path):
            try:
                response = self.session.get(image_url, timeout=10)
                if response.status_code == 200:
                    with open(image_path, "wb") as image_file:
                        image_file.write(response.content)
                    logging.info(f"Downloaded: {filename}")
                else:
                    logging.warning(f"Failed to download: {filename}")
            except requests.RequestException as e:
                logging.error(f"Error downloading {filename}: {e}")
        else:
            logging.info(f"Image already exists: {filename}, skipping.")
        time.sleep(2)  # to limit the requests per minute

    def scroll_down(self):
        try:
            last_height = self.driver.execute_script(
                "return document.body.scrollHeight"
            )
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(5)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            return new_height > last_height
        except Exception as e:
            logging.error(f"Error scrolling: {e}")
            return False

    def terminate(self):
        logging.info("Terminating the program.")
        self.driver.quit()


def main():
    logging.info("-------Starting the scraping --------")
    crawler = RedditCrawler()
    crawler.start()


if __name__ == "__main__":
    main()
