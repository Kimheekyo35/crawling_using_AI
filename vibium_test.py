import asyncio
import asyncio.streams
import sys
import re
from vibium.async_api import browser

# Monkey patch: 데이터 전송 한도 상향 (LimitOverrunError 방지)
asyncio.streams._DEFAULT_LIMIT = 100 * 1024 * 1024 

async def main():
    url = "http://numbuzin.com/product/list.html?cate_no=71"
    print(f"Vibium 브라우저 실행: {url}")
    
    # 1. 브라우저 시작
    bro = await browser.start(headless=False)
    
    try:
        # 2. 새 페이지 열기
        vibe = await bro.page()
        
        # 3. 사이트로 이동
        print(f"페이지 이동 중: {url}")
        await vibe.go(url)
        
        # 상품 목록이 렌더링될 때까지 충분히 대기
        print("상품 목록 로딩 대기 중...")
        await asyncio.sleep(7)
        
        # 4. 상품명 추출 (Selector: div.description strong.name)
        print("상품명 추출 중 (Selector: div.description strong.name)...")
        
        # li 하위의 description 영역 내 strong.name 요소를 모두 찾습니다.
        elements = await vibe.find_all("div.description strong.name")
        
        if not elements:
            print("find_all로 요소를 찾지 못했습니다. .name 클래스로 재시도합니다.")
            elements = await vibe.find_all(".name")
            
        product_names = []
        if elements:
            for el in elements:
                # 요소의 텍스트 가져오기
                text = await el.get_text()
                if text:
                    # '상품명' 글자와 콜론(:) 등을 제거하여 상품 이름만 추출
                    # 콜론이 있으면 콜론 뒤를, 없으면 '상품명' 글자 제거
                    if ":" in text:
                        name = text.split(":")[-1].strip()
                    else:
                        name = text.replace("상품명", "").strip()
                        
                    if name and name not in product_names:
                        product_names.append(name)
        
        if product_names:
            print(f"\n[추출 결과] 총 {len(product_names)}개의 상품명:")
            for idx, name in enumerate(product_names, 1):
                # 인코딩 문제 방지를 위해 안전하게 출력 시도
                try:
                    print(f"{idx}. {name}")
                except:
                    print(f"{idx}. [출력 오류 - 이름 존재함]")
        else:
            print("상품명을 찾지 못했습니다. 사이트 구조가 다르거나 로딩이 실패했을 수 있습니다.")
            
    except Exception as e:
        print(f"실행 중 오류 발생: {e}")
    finally:
        print("\n브라우저 종료 중...")
        try:
            await asyncio.wait_for(bro.stop(), timeout=3)
        except:
            pass
        
    print("Vibium 테스트가 완료되었습니다.")

if __name__ == "__main__":
    # Windows 콘솔 한글 인코딩 설정
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    asyncio.run(main())
