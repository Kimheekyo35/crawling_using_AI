import os
import re
import sys
from dataclasses import dataclass
from urllib.parse import parse_qs, quote, urlparse

from seleniumbase import SB
from selenium.webdriver.common.keys import Keys


START_URL = (
    "https://www.oliveyoung.co.kr/store/main/main.do"
    "?oy=0&t_page=4%EC%9B%94%20%EC%98%AC%EC%98%81%ED%94%BD!%20%EA%B3%BC%EB%AA%B0%EC%9E%85"
    "%20%EC%BD%9C%EB%9D%BC%EB%B3%B4%20ZIP%20%EA%B8%B0%ED%9A%8D%EC%A0%84%20%EC%83%81%EC%84%B8"
    "&t_click=%ED%97%A4%EB%8D%94&t_header_type=%EB%A1%9C%EA%B3%A0"
)
SEARCH_QUERY = "\ud4cc"


@dataclass
class ProductPrice:
    brand: str
    name: str
    original_price: str
    sale_price: str
    detail_url: str
    goods_no: str


@dataclass
class ProductReview:
    review_id: int
    option_name: str
    score: int
    useful_point: int
    created_at: str
    reviewer: str
    content: str


def clear_proxy_env() -> None:
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        os.environ.pop(key, None)


def normalize_price(raw_price: str) -> str:
    text = " ".join(raw_price.split())
    digits = "".join(re.findall(r"[\d,]+", text))
    if not digits:
        return text
    suffix = "~" if "~" in text else ""
    return f"{digits} KRW{suffix}"


def extract_goods_no(detail_url: str) -> str:
    parsed = urlparse(detail_url)
    return parse_qs(parsed.query).get("goodsNo", [""])[0]


def search_from_home(sb: SB, query: str) -> None:
    sb.uc_open_with_reconnect(START_URL, 6)
    sb.wait_for_element("#query", timeout=20)
    sb.click("#query")
    sb.clear("#query")
    sb.type("#query", query)
    sb.send_keys("#query", Keys.ENTER)
    sb.sleep(4)


def open_search_results_directly(sb: SB, query: str) -> None:
    encoded_query = quote(query)
    search_url = (
        "https://www.oliveyoung.co.kr/store/search/getSearchMain.do"
        f"?query={encoded_query}&giftYn=N"
    )
    sb.uc_open_with_reconnect(search_url, 6)
    sb.sleep(4)


def ensure_search_results_loaded(sb: SB, query: str) -> None:
    search_from_home(sb, query)
    if "getSearchMain.do" not in sb.get_current_url():
        open_search_results_directly(sb, query)

    if "Just a moment" in sb.get_title():
        sb.sleep(5)

    sb.wait_for_element(".cate_prd_list > li", timeout=20)


def extract_product_prices(sb: SB) -> list[ProductPrice]:
    cards = sb.find_elements(".cate_prd_list > li")
    products: list[ProductPrice] = []

    for card in cards:
        detail_url = card.find_element("css selector", ".prd_thumb").get_attribute("href")
        brand = card.find_element("css selector", ".tx_brand").text.strip()
        name = card.find_element("css selector", ".tx_name").text.strip()
        original_price = normalize_price(
            card.find_element("css selector", ".tx_org").text.strip()
        )
        sale_price = normalize_price(
            card.find_element("css selector", ".tx_cur").text.strip()
        )
        products.append(
            ProductPrice(
                brand=brand,
                name=name,
                original_price=original_price,
                sale_price=sale_price,
                detail_url=detail_url,
                goods_no=extract_goods_no(detail_url),
            )
        )

    return products


def fetch_top_reviews(sb: SB, goods_no: str, limit: int = 5) -> list[ProductReview]:
    response = sb.driver.execute_async_script(
        """
        const goodsNo = arguments[0];
        const limit = arguments[1];
        const done = arguments[arguments.length - 1];

        fetch("https://m.oliveyoung.co.kr/review/api/v2/reviews/cursor", {
            method: "POST",
            headers: {
                "content-type": "application/json",
                "accept": "application/json, text/plain, */*",
            },
            body: JSON.stringify({
                goodsNumber: goodsNo,
                page: 0,
                size: limit,
                sortType: "DATETIME_DESC",
                reviewType: "ALL",
            }),
        })
            .then((response) => response.json())
            .then((data) => done(data))
            .catch((error) => done({ error: String(error) }));
        """,
        goods_no,
        limit,
    )

    if not isinstance(response, dict):
        raise RuntimeError("Failed to fetch reviews: unexpected response type")

    if response.get("error"):
        raise RuntimeError(f"Failed to fetch reviews: {response['error']}")

    reviews = (response.get("data") or {}).get("goodsReviewList", [])
    return [
        ProductReview(
            review_id=review["reviewId"],
            option_name=review.get("goodsDto", {}).get("optionName", ""),
            score=review.get("reviewScore", 0),
            useful_point=review.get("usefulPoint", 0),
            created_at=review.get("createdDateTime", ""),
            reviewer=review.get("profileDto", {}).get("memberNickname", ""),
            content=" ".join(review.get("content", "").split()),
        )
        for review in reviews
    ]


def main() -> None:
    clear_proxy_env()

    with SB(uc=True, headless=True, test=True) as sb:
        ensure_search_results_loaded(sb, SEARCH_QUERY)
        products = extract_product_prices(sb)
        top_reviews: list[ProductReview] = []
        first_product = products[0] if products else None
        if first_product and first_product.goods_no:
            top_reviews = fetch_top_reviews(sb, first_product.goods_no, limit=5)

    if not products:
        print("No product prices were found for the query.")
        return

    print(f"Query '{SEARCH_QUERY}' returned {len(products)} products")
    for index, product in enumerate(products, start=1):
        print(f"{index}. Brand: {product.brand}")
        print(f"   Name: {product.name}")
        print(f"   Original price: {product.original_price}")
        print(f"   Sale price: {product.sale_price}")

    if not first_product:
        return

    print("")
    print("Top 5 latest reviews for the first product")
    print(f"Product: {first_product.name}")
    print(f"Detail URL: {first_product.detail_url}")

    if not top_reviews:
        print("No reviews were found.")
        return

    for index, review in enumerate(top_reviews, start=1):
        print(f"{index}. Reviewer: {review.reviewer}")
        print(f"   Date: {review.created_at}")
        print(f"   Score: {review.score}")
        print(f"   Option: {review.option_name}")
        print(f"   Helpful votes: {review.useful_point}")
        print(f"   Review ID: {review.review_id}")
        print(f"   Content: {review.content}")


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
