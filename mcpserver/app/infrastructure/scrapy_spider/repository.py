from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from app.core.repositories import RetrieveCourseRepository
from app.infrastructure.db.models import Course

from .spiders.course_spider import CourseSpider


class ScrapyCourseRepository(RetrieveCourseRepository):
    def __init__(self, cookies: dict | None = None):
        self.cookies = cookies

    async def get_courses(self, course_ids: list[str]) -> list[Course]:
        settings = get_project_settings()
        settings.update(
            {
                "COOKIES": self.cookies,
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
        )
        process = CrawlerProcess(settings)
        # Pass the spider class (or spider name) and init args to process.crawl()
        # CrawlerProcess.crawl expects a Spider class, name or Crawler, not an instance.
        process.crawl(CourseSpider, coursedef=",".join(course_ids))
        process.start()
        # Aquí debes manejar el resultado del spider (puedes usar signals o un pipeline)
        # Por simplicidad, asumimos que el spider devuelve un item.
        return []
