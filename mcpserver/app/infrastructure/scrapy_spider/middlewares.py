from scrapy import signals
from scrapy.http import Request

class CookieMiddleware:
    def __init__(self, cookies):
        self.cookies = cookies

    @classmethod
    def from_crawler(cls, crawler):
        s = cls(crawler.settings.get("COOKIES"))
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def spider_opened(self, spider):
        spider.cookies = self.cookies

    def process_request(self, request: Request, spider):
        if self.cookies:
            request.cookies.update(self.cookies)
        