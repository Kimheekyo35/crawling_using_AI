import asyncio
import asyncio.streams
import sys
import re
from vibium.async_api import browser

# LimitOverrunError 방지
asyncio.streams._DEFAULT_LIMIT = 100 * 1024 * 1024 

async def main():
    url = "http://numbuzin.com/product/list.html?cate_no=71"
    bro = await browser.start(headless=False)
    
    try:
        vibe = await bro.page()
        await vibe.go(url)
        await asyncio.sleep(8)
        
        # 1. 페이지 전체 텍스트 긁기
        full_text = await vibe.evaluate("document.body.innerText")
        
        # 2. 정규식으로 '상품명' 패턴을 찾아냄
        # 넘버즈인 리스트의 특징: 상품명이 한 줄로 나오고, 바로 아래 줄에 가격 정보가 있음
        # 상품명을 정교하게 찾기 위해 상품 리스트 구간을 먼저 식별
        lines = full_text.split('\n')
        extracted_names = []
        
        # 상품 리스트는 보통 '9 items' 이후에 등장함
        start_idx = 0
        for i, line in enumerate(lines):
            if '9 items' in line:
                start_idx = i
                break
        
        # 상품명 후보 리스트 추출 (가격/소비자가 정보 제외)
        for line in lines[start_idx:]:
            line = line.strip()
            # 숫자만 있거나, '원'으로 끝나거나, 너무 짧은 건 제외
            if not line or '원' in line or len(line) < 3 or 'items' in line or '인기상품' in line:
                continue
            # 이미 추출된 이름과 유사하면 패스
            if line not in extracted_names:
                extracted_names.append(line)
        
        # 실제 상품 목록 개수에 맞게 상위 9개만 출력
        final_names = extracted_names[:9]
        
        if final_names:
            print(f"\n[추출 성공] 상품명 리스트:")
            for idx, name in enumerate(final_names, 1):
                print(f"{idx}. {name}")
        else:
            print("상품명을 파싱하지 못했습니다.")
            
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

# 상품명 출력 코드 수정:
"""
gemini에 더 자세한 selector를 제시하며, 주의사항에 대해 명확히 안내하는 방식으로 수정함.
"""
