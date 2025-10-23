# playritht 离线环境安装

##  下载playright


``` python

# 方式一: pip下载: 
# playright
pip download playwright --recursive -d .

# 其他包
pip download openpyxl pandas python-calamine ttkbootstrap pyinstaller --recursive -d .

# 方式二: 浏览器下载:
https://pypi.org/project/playwright/#files

```

## 下载浏览器驱动
``` python
# playwright install chromium
# 方式一：下载浏览器驱动
playwright install --dry-run

# 方式二：运行以下 Python 脚本下载浏览器驱动
import playwright
playwright.install()

#下载后的驱动默认位于：
# Windows: %LOCALAPPDATA%\ms-playwright
# Linux/macOS: ~/.cache/ms-playwright
```

## 配置浏览器驱动
``` python
# 方式一、复制驱动到默认路径
Windows: %LOCALAPPDATA%\ms-playwright
Linux/macOS: ~/.cache/ms-playwright

# 方式二、通过环境变量指定驱动路径
# Linux/macOS
export PLAYWRIGHT_BROWSERS_PATH=/path/to/your/playwright_offline/ms-playwright

# Windows (PowerShell)
$env:PLAYWRIGHT_BROWSERS_PATH = "C:\path\to\your\playwright_offline\ms-playwright"

# 3、在脚本中直接设置路径
playwright.install(browsers_path="/path/to/drivers")

```

## 安装离线包
``` python

pip install --no-index --find-links=. playwright

```


## 验证安装
``` python
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://www.baidu.com")
        print(await page.title())
        await browser.close()

asyncio.run(main())

```



## Note: requirements.txt
``` python

pip list --format=freeze > requirements.txt
pip freeze > requirements.txt

pip download -r requirements.txt  -d /path/to/download/dir

pip install --no-index --find-links=./offline_packages -r requirements.txt

```

## Note: 浏览器离线安装包

``` python
# chrome
chrome 64位：
https://dl.google.com/tag/s/installdataindex/update2/installers/ChromeStandaloneSetup64.exe

chrome 32位：
https://dl.google.com/tag/s/installdataindex/update2/installers/ChromeStandaloneSetup.exe

# edge
Edge 商业版下载页面（支持选择版本）：
https://www.microsoft.com/edge/business/download
可选择 稳定版（Stable）、Beta 版、Dev 版，并下载对应的 .msi 或 .exe 离线安装包57。

方法 2：从已安装 Edge 的电脑提取离线包
在已联网的电脑上安装 Edge（在线安装）。
进入目录：
C:\Program Files (x86)\Microsoft\EdgeUpdate\Download\
找到类似 MicrosoftEdge_X64_版本号.exe 的文件，即为离线安装包

# firefox
方法 1：Mozilla 官网下载（最新版）
国际版（原版）离线安装包：
https://www.mozilla.org/en-US/firefox/all/
选择 操作系统（Windows 32/64位、Mac、Linux）和语言，下载完整安装包410。

方法 2：Mozilla FTP 服务器（所有历史版本）
Firefox 所有版本离线包：
http://ftp.mozilla.org/pub/firefox/releases/
可下载 旧版本、Beta 版、ESR（长期支持版
```

