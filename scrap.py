from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import multiprocessing

url = "https://www.amazon.com/ref=nav_logo?language=zh_TW"
def open_amazon(keyword, shared_results):
    options = Options()
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--start-maximized")
    options.add_argument("headless")
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    try:
        search_bar = driver.find_element(By.ID, "twotabsearchtextbox")
    except NoSuchElementException:
        search_bar = driver.find_element(By.ID, "nav-bb-search")
    search_bar.send_keys(keyword)
    search_bar.submit()
    for _ in range(5):
        driver.execute_script("window.scrollBy(0, 1000);")
    list_items = driver.find_elements(By.XPATH, "//div[@role='listitem']")
    searched_items = []
    for item in list_items:
        try:
            name = item.find_element(By.TAG_NAME, "h2").text
            href = item.find_element(By.TAG_NAME, "a").get_attribute("href")
            price = float(item.find_element(By.CLASS_NAME, "a-price-whole").text)
            if item.find_element(By.CLASS_NAME, "a-price-fraction").text:
                price += float(item.find_element(By.CLASS_NAME, "a-price-fraction").text) / 100
            searched_items.append({"name": name, "href": href, "price": price})
        except:
            name = "No name"
            href = "No href"
            price = "No price"
    #     print(name, price)
    # print(searched_items)
    shared_results.append(searched_items)
    driver.quit()

# 創建一個進程來平行處理
def search_amazon(keyword):
    # 使用多進程來處理
    with multiprocessing.Manager() as manager:
        results = manager.list()  # 共享的 list
        process1 = multiprocessing.Process(target=open_amazon, args=(keyword,results))
        process2 = multiprocessing.Process(target=open_amazon, args=(keyword,results))
        process3 = multiprocessing.Process(target=open_amazon, args=(keyword,results))
        # 啟動進程
        process1.start()
        process2.start()
        process3.start()
        # 等待進程結束
        process1.join()
        process2.join()
        process3.join()
        longest_list = max(results, key=len)
        # 美金轉台幣
        for list in longest_list:
            list["price"] = 32.71 * list["price"]
        return longest_list


# if __name__ == "__main__":
#     search_amazon("筆電")