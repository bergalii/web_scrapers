import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests
import os
import re
import json

# Default variables
CHROME_OPTIONS = uc.ChromeOptions()
CHROME_OPTIONS.headless = True
LOGIN_URL = login_url = (
    "https://www.amazon.de/-/en/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.de%2F%3Fref_%3Dnav_signin&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=deflex&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"
)

MAIN_PAGE_URL = "https://www.amazon.de/"


class AmazonCrawler:
    def __init__(self):
        self.driver = uc.Chrome(use_subprocess=True, options=CHROME_OPTIONS)
        # login credentials
        self.email = ""
        self.password = ""
        self.timeout = 20  # in seconds
        self.wait = WebDriverWait(self.driver, self.timeout)
        self.loop = True
        self.folder_path = "./images"  # Folder to save the images
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)
        # Keywords to search in Amazon
        self.keywords = [
            "women's jeans",
            "women's pants",
            "women's trousers",
            "women's dresses",
            "women's pullover",
            "women's sweater",
            "women's hoodie",
            "women's coat",
            "women's jacket",
            "women's jumpsuit",
            "lingerie",
            "women's bodywear",
            "women's maternity",
            "women's nightwear",
            "women's shorts",
            "women's skirt",
            "women's socks",
            "pantyhose",
            "women's swimwear",
            "women's t-shirt",
            "women's top",
            "women's blouse",
            "women's boots",
            "women's shoes",
            "women's slippers",
            "women's sports clothing",
            "women's hat",
            "women's cap",
            "men's jeans",
            "men's nightwear",
            "men's pants",
            "men's pullover",
            "men's sweater",
            "men's hoodie",
            "men's coat",
            "men's jacket",
            "men's jumpsuit",
            "men's bodywear",
            "men's shorts",
            "men's socks",
            "men's swimwear",
            "men's t-shirt",
            "men's top",
            "men's boots",
            "men's shoes",
            "men's slippers",
            "men's sports clothing",
            "men's hat",
            "men's cap",
        ]
        self.product_urls = []
        self.ratings_threshold = 500
        self.page_depth = 5
        self.current_page = 1
        self.starting_keyword = self.keywords[0]
        self.review_threshold = ["1 Star", "2 Stars", "3 Stars"]
        self.session = requests.Session()
        self.mount_retry_adapter()

    def save_state(self, keyword):
        """Save the current state to a JSON file."""

        state = {"starting_keyword": keyword}
        with open("./state.json", "w") as f:
            json.dump(state, f)

    def load_state(self):
        """Load the last saved state."""

        try:
            with open("./state.json", "r") as f:
                state = json.load(f)
                self.starting_keyword = state["starting_keyword"]

        except FileNotFoundError:
            print("No saved state found, starting from the scratch.")

    def login(self):
        """Login to a Amazon account with given credentials"""

        self.driver.get(LOGIN_URL)
        print("-------- Logging into the Amazon account -------------")
        # Give the e-mail account
        email = self.wait.until(EC.element_to_be_clickable((By.ID, "ap_email")))
        email.clear()
        email.send_keys(self.email)
        self.wait.until(EC.element_to_be_clickable((By.ID, "continue"))).click()

        # Give the password & sign in
        password = self.wait.until(EC.element_to_be_clickable((By.ID, "ap_password")))
        password.clear()  # Clear the field before sending keys
        password.send_keys(self.password)
        self.wait.until(EC.element_to_be_clickable((By.ID, "signInSubmit"))).click()

    def is_logged_in(self):
        """Check if the login was successful"""
        try:
            # Look for an element that is only visible when logged in, such as 'Account' link
            navbar_logo = self.wait.until(
                EC.visibility_of_element_located((By.ID, "nav-logo-sprites"))
            )
            return True if navbar_logo else False
        except TimeoutException:
            return False

    def search(self, keyword):
        """Go to search results page for the given keyword"""

        # Go to main page first
        self.driver.get(MAIN_PAGE_URL)
        search_bar = self.wait.until(
            EC.element_to_be_clickable((By.ID, "twotabsearchtextbox"))
        )
        search_bar.clear()
        search_bar.send_keys(keyword)
        self.wait.until(
            EC.element_to_be_clickable((By.ID, "nav-search-submit-button"))
        ).click()

    def get_product_urls(self, keyword):
        """Collect the product page urls for the given keyword"""

        print(f'Getting results for "{keyword}"')
        # Go to search results
        self.search(keyword)
        self.current_page = 1
        # Go through pages
        while self.current_page <= self.page_depth:
            # Get the urls in the current page
            self.fetch_currentpage_urls()
            # Find the 'Next' button and click to navigate to the next page
            try:
                next_page_button = self.wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.CSS_SELECTOR,
                            "a.s-pagination-item.s-pagination-next.s-pagination-button.s-pagination-separator",
                        )
                    )
                )
                if next_page_button.is_enabled():
                    next_page_button.click()
                    self.current_page += 1
                else:
                    break

            except Exception as e:
                print("No more pages or encountered an error:", e)
                break

    def fetch_currentpage_urls(self):
        """Collect product urls in the current page that have ratings above the threshold"""

        # Get the product review information for each product
        elements = self.wait.until(
            EC.presence_of_all_elements_located(
                (
                    By.XPATH,
                    '//span[@data-csa-c-content-id="alf-customer-ratings-count-component"]',
                )
            )
        )

        # Add all the urls of the products that have reviews above the threshold to the array
        for element in elements:
            ratings_count = element.find_element(
                By.XPATH, './/span[contains(@aria-label, " ratings")]'
            ).get_attribute("aria-label")

            # Extract the number from the label using regular expression
            match = re.search(r"(\d+,\d+)", ratings_count)
            if match:
                ratings_count = int(match.group(1).replace(",", ""))
                if ratings_count > self.ratings_threshold:
                    # Get the href attribute from the child <a> element
                    product_url = element.find_element(By.XPATH, ".//a").get_attribute(
                        "href"
                    )
                    self.product_urls.append(product_url)

    def crawl(self):
        """Go through the product urls and download review images"""

        print(f"{len(self.product_urls)} products found, starting with the crawling.")
        for i, product_url in enumerate(self.product_urls, start=1):
            try:
                self.loop = True
                # Go to product page
                self.driver.get(product_url)

                print(
                    f'Collecting images for the product "{self.get_product_title()}" [{i}/{len(self.product_urls)}]'
                )
                # Click "See all photos" button
                self.click_element(
                    "//div[@data-csa-c-slot-id='cm_cr_dp_see_all_image_carousel_reviews']/a[@class='a-link-emphasis']"
                )

                # Click on the first image to enlarge it
                self.click_element(
                    "//button[@data-mix-operations='galleryItemClickHandler']"
                )

                # Now go through the images and download them
                self.loop_through_images()

            except TimeoutException as e:
                print(
                    "No images found for the product, continuing with the next product."
                )
            except Exception as general_error:
                print(
                    "An unexpected error occurred, continuing with the next product.",
                    general_error,
                )
        # After it's completed reset the urls
        self.product_urls = []

    def get_product_title(self):
        title_element = self.wait.until(
            EC.visibility_of_element_located((By.ID, "productTitle"))
        )
        product_title = title_element.text.strip()
        return product_title

    def loop_through_images(self):
        """Go through the reviews, and download the images"""

        while self.loop:
            try:
                rating = self.get_rating()
                if rating in self.review_threshold:
                    image = self.wait.until(
                        EC.visibility_of_element_located(
                            (
                                By.XPATH,
                                "//div[contains(@class, 'media-popover-image-view-active')]/img[contains(@class, 'media-popover-image-view')]",
                            )
                        )
                    )
                    self.download_image(image.get_attribute("src"))
                    self.next_image()
                else:
                    self.next_image()
            except TimeoutException as e:
                print("Timeout error, skipping to the next image...")
                self.next_image()
            except Exception as e:
                print("An error occurred: ", e)
                self.terminate()
                break

    def get_rating(self):

        rating_element = self.wait.until(
            EC.visibility_of_element_located(
                (By.XPATH, "//i[@data-reviewbind='Rating']")
            )
        )
        # Use a JS script to get the rating text
        rating = self.driver.execute_script(
            "return arguments[0].firstElementChild.textContent;", rating_element
        ).strip()

        return rating

    def next_image(self):
        """Go to the next image in the gallery"""

        try:
            self.click_element("//button[@data-mix-operations='rightClickHandler']")
        except TimeoutException:
            print("No more images to navigate, continuing with the next product.")
            self.loop = False

    def download_image(self, image_url):
        """Download the image to a specified folder"""

        filename = os.path.basename(image_url)
        image_path = os.path.join(self.folder_path, filename)
        response = self.session.get(image_url)

        # If image already exists terminate the loop
        if os.path.exists(image_path):
            print(f"Image already exists: {filename}, skipping to the next product.")
            self.loop = False
        else:
            if response.status_code == 200:
                with open(image_path, "wb") as image_file:
                    image_file.write(response.content)
                print(f"Downloaded: {filename}")
            else:
                print(f"Failed to download: {filename}")

    def click_element(self, xpath):
        element = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        element.click()

    def start(self):
        """Start the pipeline"""

        try:
            self.login()
            if self.is_logged_in():
                print(
                    "---------- Successfully logged in, starting the crawling process. ----------"
                )
                for i, keyword in enumerate(self.keywords):
                    # Save the current keyword
                    self.save_state(keyword)
                    if keyword != self.starting_keyword:
                        print(
                            f'Results for "{keyword}" are already collected, continuing with the next one.'
                        )
                        continue
                    self.get_product_urls(keyword)
                    self.crawl()
                    self.starting_keyword = self.keywords[i + 1]
                print("------ Crawling process has been successfully completed. ------")

        finally:
            self.terminate()

    def terminate(this):
        print("Terminating the program.")
        this.driver.quit()

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


def main():
    print("------- Welcome --------")
    crawler = AmazonCrawler()
    crawler.load_state()
    crawler.start()


if __name__ == "__main__":
    main()
