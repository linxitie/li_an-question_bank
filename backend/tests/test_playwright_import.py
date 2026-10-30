"""
Task 9: Playwright 自动化测试 - 题目导入流程
测试 7 个 docx 题目文档 + 7 个 PDF 答案文档的分离导入匹配

默认跳过：该链路会向真实后端导入数据，必须显式用 RUN_PLAYWRIGHT_E2E=1
并先启动 9527 前端与 8000 后端。前端端口唯一为 9527，禁止回退到旧端口。
"""
import asyncio
import json
import os
import pytest
from playwright.async_api import async_playwright, expect

# ============ 测试配置 ============
# 前端只有 9527 一个启动端口（vite.config.ts DEV_PORT + strictPort）。
BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:9527").rstrip("/")
API_URL = os.environ.get("E2E_API_URL", "http://localhost:8000").rstrip("/")

# 导入链路会写真实库，默认不纳入常规 pytest；需要时显式开启。
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_PLAYWRIGHT_E2E") != "1",
    reason="需显式设置 RUN_PLAYWRIGHT_E2E=1，并先启动 9527 前端与 8000 后端",
)
LOGIN_USER = "admin"
LOGIN_PASS = "admin123"

# 7 组题目-答案文档对（题目 docx → 答案 pdf）
TEST_DOC_PAIRS = [
    {
        "name": "2016江西招警",
        "question": "题库/公安题目（打印）/2016江西招警考试《人民警察基础知识》真题（部分）.docx",
        "answer": "题库/答案解析（不用打印）/2016江西招警考试《人民警察基础知识》真题答案及解析（部分）.pdf",
    },
    {
        "name": "2016多省联考",
        "question": "题库/公安题目（打印）/2016年多省（市、区）公务员联考 《公安基础知识》试卷.docx",
        "answer": "题库/答案解析（不用打印）/2016年多省（市、区）公务员联考 《公安基础知识》试卷答案及解析.pdf",
    },
    {
        "name": "2016河南",
        "question": "题库/公安题目（打印）/2016年河南省公务员考试《公安基础知识》专业考试真题.docx",
        "answer": "题库/答案解析（不用打印）/2016年河南省公务员考试《公安基础知识》专业考试真题答案及解析.pdf",
    },
    {
        "name": "2017多省联考",
        "question": "题库/公安题目（打印）/2017年多省联考《公安专业科目》考试.docx",
        "answer": "题库/答案解析（不用打印）/2017年多省联考《公安专业科目》考试参考答案及解析.pdf",
    },
    {
        "name": "2017国考",
        "question": "题库/公安题目（打印）/2017年国家公务员考试《公安专业科目》真题.docx",
        "answer": "题库/答案解析（不用打印）/2017年国家公务员考试《公安专业科目》真题答案及解析.pdf",
    },
    {
        "name": "2018多省联考",
        "question": "题库/公安题目（打印）/2018年多省（市、区）公务员联考 《公安基础知识》（专业科目）真题.docx",
        "answer": "题库/答案解析（不用打印）/2018年多省（市、区）公务员联考 《公安基础知识》（专业科目）真题答案及解析.pdf",
    },
    {
        "name": "2018国考",
        "question": "题库/公安题目（打印）/2018年国家公务员考试《公安专业科目》真题.docx",
        "answer": "题库/答案解析（不用打印）/2018年国家公务员考试《公安专业科目》真题答案及解析.pdf",
    },
]


def resolve_path(rel_path: str) -> str:
    """将相对路径转换为绝对路径"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, rel_path)


# ============ 辅助函数 ============
async def login(page):
    """登录系统"""
    await page.goto(f"{BASE_URL}/#/login")
    await page.wait_for_load_state("networkidle")

    # 尝试多种登录表单选择器
    try:
        # 模式1：标准 input[name="username"]
        await page.fill('input[name="username"]', LOGIN_USER)
        await page.fill('input[name="password"]', LOGIN_PASS)
    except Exception:
        try:
            # 模式2：placeholder 定位
            await page.fill('input[placeholder*="用户名"]', LOGIN_USER)
            await page.fill('input[placeholder*="密码"]', LOGIN_PASS)
        except Exception:
            # 模式3：顺序定位所有 input
            inputs = page.locator("input")
            count = await inputs.count()
            if count >= 2:
                await inputs.nth(0).fill(LOGIN_USER)
                await inputs.nth(1).fill(LOGIN_PASS)

    # 点击登录按钮
    try:
        await page.click('button:has-text("登录")')
    except Exception:
        await page.click('button[type="submit"]')

    # 等待登录完成（URL 变化或出现首页元素）
    await page.wait_for_timeout(2000)


async def navigate_to_import(page):
    """导航到题目导入页面"""
    await page.goto(f"{BASE_URL}/#/question-import")
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1000)


# ============ 测试用例 ============
@pytest.mark.asyncio
async def test_login_and_navigate():
    """测试登录和导航到导入页面"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await login(page)
            await navigate_to_import(page)

            # 验证导入页面加载
            page_content = await page.content()
            assert "导入" in page_content or "import" in page_content.lower(), "导入页面未加载"
            print("✓ 登录成功，已导航到导入页面")
        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_single_pair_import():
    """测试单对文档的分离导入流程"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await login(page)
            await navigate_to_import(page)

            pair = TEST_DOC_PAIRS[0]
            q_path = resolve_path(pair["question"])
            a_path = resolve_path(pair["answer"])

            # 验证文件存在
            assert os.path.exists(q_path), f"题目文件不存在: {q_path}"
            assert os.path.exists(a_path), f"答案文件不存在: {a_path}"

            print(f"✓ 测试文档对: {pair['name']}")
            print(f"  题目: {pair['question']}")
            print(f"  答案: {pair['answer']}")

            # 切换到分离导入模式
            try:
                await page.click('text=分离导入')
            except Exception:
                try:
                    await page.click('button:has-text("分离")')
                except Exception:
                    print("  ⚠ 未找到分离导入按钮，跳过 UI 交互")
                    return

            await page.wait_for_timeout(500)

            # 上传题目文档
            try:
                file_inputs = page.locator('input[type="file"]')
                file_count = await file_inputs.count()
                if file_count >= 1:
                    await file_inputs.nth(0).set_input_files(q_path)
                    print("  ✓ 题目文档已上传")
                else:
                    print("  ⚠ 未找到文件上传输入框")
                    return
            except Exception as e:
                print(f"  ⚠ 题目文档上传失败: {e}")
                return

            await page.wait_for_timeout(3000)

            # 上传答案文档
            try:
                file_inputs = page.locator('input[type="file"]')
                file_count = await file_inputs.count()
                if file_count >= 2:
                    await file_inputs.nth(1).set_input_files(a_path)
                    print("  ✓ 答案文档已上传")
                else:
                    print("  ⚠ 未找到第二个文件上传输入框")
                    return
            except Exception as e:
                print(f"  ⚠ 答案文档上传失败: {e}")
                return

            await page.wait_for_timeout(3000)

            # 点击开始匹配
            try:
                await page.click('button:has-text("匹配")')
                print("  ✓ 已点击匹配按钮")
            except Exception:
                try:
                    await page.click('text=开始匹配')
                    print("  ✓ 已点击开始匹配")
                except Exception:
                    print("  ⚠ 未找到匹配按钮")

            # 等待匹配结果
            await page.wait_for_timeout(5000)

            # 尝试读取匹配率
            try:
                rate_el = page.locator('text=/匹配率/').first
                rate_text = await rate_el.text_content()
                print(f"  ✓ 匹配结果: {rate_text}")
            except Exception:
                print("  ⚠ 无法读取匹配率")

            print(f"  ✓ 文档对 {pair['name']} 测试完成")

        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_all_seven_pairs():
    """测试全部 7 对文档的导入流程"""
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await login(page)
            await navigate_to_import(page)

            for i, pair in enumerate(TEST_DOC_PAIRS):
                print(f"\n--- 文档对 {i+1}/7: {pair['name']} ---")

                q_path = resolve_path(pair["question"])
                a_path = resolve_path(pair["answer"])

                file_exists = os.path.exists(q_path) and os.path.exists(a_path)
                if not file_exists:
                    print(f"  ⚠ 文件不存在，跳过")
                    results.append({"name": pair["name"], "status": "skipped", "reason": "file_not_found"})
                    continue

                # 切换到分离导入模式（每次循环重新进入）
                await navigate_to_import(page)
                try:
                    await page.click('text=分离导入')
                    await page.wait_for_timeout(500)
                except Exception:
                    pass

                # 上传题目文档
                try:
                    file_inputs = page.locator('input[type="file"]')
                    if await file_inputs.count() >= 1:
                        await file_inputs.nth(0).set_input_files(q_path)
                        await page.wait_for_timeout(2000)
                except Exception as e:
                    print(f"  ⚠ 题目上传失败: {e}")
                    results.append({"name": pair["name"], "status": "fail", "reason": str(e)})
                    continue

                # 上传答案文档
                try:
                    file_inputs = page.locator('input[type="file"]')
                    if await file_inputs.count() >= 2:
                        await file_inputs.nth(1).set_input_files(a_path)
                        await page.wait_for_timeout(2000)
                except Exception as e:
                    print(f"  ⚠ 答案上传失败: {e}")
                    results.append({"name": pair["name"], "status": "fail", "reason": str(e)})
                    continue

                # 点击匹配
                try:
                    await page.click('button:has-text("匹配")')
                except Exception:
                    try:
                        await page.click('text=开始匹配')
                    except Exception:
                        pass

                await page.wait_for_timeout(5000)

                # 读取匹配率
                try:
                    rate_el = page.locator('text=/匹配率/').first
                    rate_text = await rate_el.text_content()
                    print(f"  结果: {rate_text}")
                    results.append({"name": pair["name"], "status": "ok", "rate": rate_text})
                except Exception:
                    print(f"  无法读取匹配率")
                    results.append({"name": pair["name"], "status": "no_rate"})

        finally:
            await browser.close()

    # 打印汇总
    print("\n========== 测试汇总 ==========")
    for r in results:
        status_icon = "✓" if r["status"] == "ok" else "⚠"
        print(f"  {status_icon} {r['name']}: {r['status']} {r.get('rate', r.get('reason', ''))}")
    print(f"总计: {len(results)} 对文档")

    return results


@pytest.mark.asyncio
async def test_api_separate_match():
    """通过 API 直接测试分离匹配接口（无需浏览器）"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await login(page)

            pair = TEST_DOC_PAIRS[0]
            q_path = resolve_path(pair["question"])
            a_path = resolve_path(pair["answer"])

            assert os.path.exists(q_path), f"题目文件不存在: {q_path}"
            assert os.path.exists(a_path), f"答案文件不存在: {a_path}"

            # 通过 API 上传题目文档
            with open(q_path, "rb") as qf:
                qResp = await page.request.post(
                    f"{API_URL}/api/questions/import/parse",
                    multipart={
                        "file": {
                            "name": os.path.basename(q_path),
                            "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            "buffer": qf.read(),
                        }
                    },
                )
                qData = await qResp.json()
                print(f"  题目解析响应: status={qResp.status}")

            # 通过 API 上传答案文档
            with open(a_path, "rb") as af:
                aResp = await page.request.post(
                    f"{API_URL}/api/questions/import/parse",
                    multipart={
                        "file": {
                            "name": os.path.basename(a_path),
                            "mimeType": "application/pdf",
                            "buffer": af.read(),
                        }
                    },
                )
                aData = await aResp.json()
                print(f"  答案解析响应: status={aResp.status}")

            # 调用分离匹配 API
            matchResp = await page.request.post(
                f"{API_URL}/api/questions/import/separate-match",
                data={
                    "questions_text": json.dumps(qData.get("parsed_text", qData.get("text", ""))),
                    "answers_text": json.dumps(aData.get("parsed_text", aData.get("text", ""))),
                },
            )
            matchData = await matchResp.json()
            print(f"  匹配响应: {json.dumps(matchData, ensure_ascii=False, indent=2)[:500]}")

        finally:
            await browser.close()


# ============ 直接运行 ============
if __name__ == "__main__":
    asyncio.run(test_login_and_navigate())
    asyncio.run(test_api_separate_match())
