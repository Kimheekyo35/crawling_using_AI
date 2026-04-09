import asyncio
from vibium.async_api import browser

async def main():
    print("Vibium 브라우저를 시작합니다...")
    # 1. 브라우저 시작
    bro = await browser.start()
    
    # 2. 새 페이지(Vibe) 열기
    vibe = await bro.page()
    
    # 3. Google로 이동
    print("Google로 이동 중...")
    await vibe.go("https://www.google.com")
    
    # 4. 검색창(textarea) 찾기 및 텍스트 입력
    # (Vibium은 시맨틱하게 요소를 찾을 수 있습니다)
    search_box = await vibe.find("textarea")
    if search_box:
        print("검색어를 입력합니다...")
        await search_box.type("Vibium browser automation framework")
        await search_box.press("Enter")
    
    # 5. 잠시 대기 후 브라우저 종료
    print("검색 결과를 확인하기 위해 잠시 대기합니다...")
    await asyncio.sleep(5)
    
    await bro.stop()
    print("Vibium 테스트가 완료되었습니다.")

if __name__ == "__main__":
    asyncio.run(main())

