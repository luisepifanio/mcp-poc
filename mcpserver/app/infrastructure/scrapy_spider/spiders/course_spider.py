import json
import logging

import scrapy
from scrapy.http.response.html import HtmlResponse
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)


class CourseSpider(scrapy.Spider):
    name = "course_lti"

    custom_settings = {
        "USER_AGENT": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
        "COOKIES_ENABLED": True,
        "COOKIES_DEBUG": True,  # Optional, for debugging
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",  # Choose 'chromium', 'firefox', or 'webkit'
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,  # Set to False if you want to see the browser
        },
    }

    def __init__(self, coursedef: str | list[str] | None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.debug(f"Initialized CourseSpider with course_ids: {coursedef}")

        self.allowed_domains = ["campus.europaeducationgroup.es"]
        courses: list[str] = []
        if isinstance(coursedef, str):
            if "," in coursedef:
                courses += coursedef.split(",")
            elif " " in coursedef:
                courses += coursedef.split(" ")
            else:
                courses = [coursedef]
        elif isinstance(coursedef, list):
            courses += coursedef

        cookies: dict = {}
        with open("var/lib/cookies.json") as f:
            cookies.update(json.load(f))

        self.custom_settings = self.custom_settings or {}
        self.custom_settings.update(
            {
                "COOKIES": cookies,
                "workload": [
                    {
                        "course_id": course_id,
                        "url": f"https://campus.europaeducationgroup.es/courses/{course_id}/external_tools/426",
                    }
                    for course_id in courses
                ],
            }
        )

    async def start(self):
        workload = (self.custom_settings or {}).get("workload", [])

        for workitem in workload:
            course_id = workitem["course_id"]
            url = workitem["url"]
            yield scrapy.Request(
                url=url,
                cookies=self.custom_settings.get("COOKIES"),  # type: ignore
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod(
                            "wait_for_selector",
                            "iframe.tool_launch",
                        ),
                        PageMethod(
                            "wait_for_selector",
                            "iframe.tool_launch >> button.nav-link.active",
                            timeout=10000,
                        ),
                        PageMethod("wait_for_load_state", "networkidle"),
                    ],
                },
                callback=self.parse,  # type: ignore
                errback=self.errback,
                cb_kwargs={"course_id": course_id},
            )

    def parse(self, response: HtmlResponse, course_id: str):
        # logger.info(f"response is {type(response)}")
        logger.info(f"Scraping course page for course_id: {course_id}")
        try:
            # Ejemplo: Extraer datos del curso
            title = response.css("h1::text").get()
            description = response.css(".description::text").get()
            yield {
                "id": course_id,
                "title": title,
                "description": description,
            }
        except Exception as e:
            logger.error(f"Error parsing course {course_id}: {e}")
            yield {"id": course_id, "error": str(e)}

    def errback(self, failure):
        course_id = failure.request.cb_kwargs.get("course_id", "unknown")
        logger.error(f"Error scraping course {course_id}: {failure.getTraceback()}")
        yield {"id": course_id, "error": str(failure)}
