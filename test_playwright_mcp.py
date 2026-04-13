import asyncio
import io
import sys

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright


SEARCH_URL = "https://www.youtube.com/results?search_query=%EC%A0%95%EC%9E%AC%ED%98%84"


async def fetch_top_video_titles() -> list[str]:
    try:
        playwright_context = async_playwright()
        playwright = await playwright_context.__aenter__()
    except PermissionError as exc:
        raise RuntimeError(
            "Playwright 브라우저 프로세스를 시작하지 못했습니다. "
            "샌드박스나 보안 정책 때문에 하위 프로세스 생성이 차단된 환경일 수 있습니다."
        ) from exc

    try:
        browser = await playwright.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            await page.goto(SEARCH_URL, wait_until="domcontentloaded")

            # Regional consent dialogs are intermittent; ignore if they do not appear.
            try:
                await page.get_by_role("button", name="Accept all").click(timeout=3000)
            except PlaywrightTimeoutError:
                try:
                    await page.get_by_role("button", name="모두 수락").click(timeout=3000)
                except PlaywrightTimeoutError:
                    pass

            await page.wait_for_selector("ytd-video-renderer #video-title", timeout=15000)
            titles = await page.locator("ytd-video-renderer #video-title").evaluate_all(
                """
                nodes => nodes
                    .slice(0, 5)
                    .map(node => (node.getAttribute('title') || node.textContent || '').trim())
                    .filter(Boolean)
                """
            )
            return titles
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(
                "유튜브 검색 결과에서 동영상 제목을 찾지 못했습니다. "
                "페이지 구조가 바뀌었거나 동의 배너 때문에 결과가 가려졌을 수 있습니다."
            ) from exc
        finally:
            await browser.close()
    finally:
        await playwright_context.__aexit__(None, None, None)


async def main() -> None:
    try:
        titles = await fetch_top_video_titles()
    except Exception as exc:
        print(f"오류: {exc}")
        return

    if not titles:
        print("동영상 제목을 가져오지 못했습니다.")
        return

    print("유튜브 검색어 '정재현' 상위 5개 동영상 제목")
    for index, title in enumerate(titles, start=1):
        print(f"{index}. {title}")


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    asyncio.run(main())
