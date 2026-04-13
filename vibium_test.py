import asyncio
import asyncio.streams
import sys
from vibium.async_api import browser

# LimitOverrunError 방지
asyncio.streams._DEFAULT_LIMIT = 100 * 1024 * 1024 

async def main():
    url = "http://numbuzin.com/product/list.html?cate_no=71"
    
    bro = await browser.start(headless=False)
    
    try:
        vibe = await bro.page()
        await vibe.go(url)
        await asyncio.sleep(5)
        
        # 브라우저에서 상품 데이터를 직접 파싱
        products = await vibe.evaluate("""
            () => {
                const results = [];
                // li 요소 중 상품 정보가 담긴 것만 선택
                const items = document.querySelectorAll('li[id^="anchorBoxId_"]');
                items.forEach(item => {
                    const text = item.innerText;
                    const lines = text.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
                    
                    // 넘버즈인 리스트 구조상 상품명이 보통 첫 번째나 두 번째 줄에 있음
                    let name = "";
                    let salePrice = "";
                    let customPrice = "";
                    
                    for(let line of lines) {
                        if (line.includes('원') && !name) continue; // 가격이 먼저 나오면 패스
                        if (!name && line.length > 3) name = line;
                        else if (line.match(/\\d{1,3}(,\\d{3})*원/)) {
                            if (!salePrice) salePrice = line;
                            else if (!customPrice) customPrice = line;
                        }
                    }
                    
                    if (name) {
                        results.push({name, salePrice, customPrice});
                    }
                });
                return results;
            }
        """)
        
        if products:
            print(f"\n[추출 성공] {len(products)}개 상품:")
            for idx, p in enumerate(products, 1):
                print(f"{idx}. 제품명: {p['name']}")
                print(f"   할인 후: {p['salePrice']}")
                print(f"   할인 전: {p['customPrice']}")
                print("-" * 30)
    except Exception as e:
        print(f"오류: {e}")
    finally:
        try:
            await asyncio.wait_for(bro.stop(), timeout=3)
        except:
            pass

if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    asyncio.run(main())
