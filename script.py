import json
import os
from datetime import datetime
import time
import requests
from bs4 import BeautifulSoup
from pytrends.request import TrendReq
import re
import pytz
import random

def get_trends(geo='US', timeframe='today 1-m'):
    pytrends = TrendReq(hl='en-US', tz=360, timeout=(10, 25))
    pytrends.build_payload(kw_list=[' '], cat=0, timeframe=timeframe, geo=geo, gprop='')
    trends_df = pytrends.trending_searches(pn='united_states')
    trends = trends_df[0].tolist()
    return trends

def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def search_and_scrape(keyword, num_articles=5):
    search_url = f"https://www.google.com/search?q={keyword}+in+english&num={num_articles}"
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    ]
    headers = {
        "User-Agent": random.choice(user_agents)
    }
    try:
        response = requests.get(search_url, headers=headers, timeout=(10, 25))
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        search_results = soup.find_all("div", class_="tF2Cxc")
        articles = []
        for result in search_results:
            try:
                link = result.find("a")["href"]
                article_response = requests.get(link, headers=headers, timeout=(10, 25))
                article_response.raise_for_status()
                article_soup = BeautifulSoup(article_response.content, "html.parser")
                title = article_soup.find("title").text if article_soup.find("title") else ""
                paragraphs = article_soup.find_all("p")
                content = ""
                for p in paragraphs:
                    content += p.text + " "
                content = clean_text(content)

                if content and len(content.split()) > 100:
                    articles.append({"title": title, "content": content, "url": link})
                    print(f"文章 {link} 已添加，单词数：{len(content.split())}")
                else:
                    print(f"文章 {link} 内容过短或为空, 已丢弃")
                time.sleep(random.uniform(1, 3))
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                  print(f"爬取 {link} 失败: 403 错误")
                else:
                  print(f"爬取 {link} 失败: {e}")
            except Exception as e:
                print(f"爬取 {link} 失败: {e}")

        return articles
    except requests.exceptions.RequestException as e:
        print(f"搜索 {keyword} 失败: {e}")
        return []

def translate(text, max_retries=5, retry_delay=5):
    api_base = os.environ["OPENAI_API_BASE"]
    api_key = os.environ["OPENAI_API_KEY"]
    model = os.environ["OPENAI_API_MODEL"]
    prompt = "你是一位专业的翻译助理，请将以下英文文本翻译成流畅、准确且符合中文表达习惯的中文。请务必保持原文意思不变，并尽可能保留原文的风格和语气。如果文本中包含专有名词或术语，请确保翻译准确。如果文本中存在一些难以直译的部分，请根据上下文进行意译，并确保译文通顺易懂。翻译后的文本应尽可能符合中文的语法和表达习惯，避免出现生硬的翻译腔。请直接输出翻译后的中文文本，无需添加任何额外的解释或说明。\n\n"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ]
    }
    retries = 0
    while retries < max_retries:
        try:
            response = requests.post(api_base, headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            translated_text = response.json()['choices'][0]['message']['content'].strip()
            return translated_text
        except requests.exceptions.RequestException as e:
            print(f"翻译出错: {e}")
            retries += 1
            print(f"进行第 {retries} 次重试，将在 {retry_delay} 秒后重试...")
            time.sleep(retry_delay)
        except (KeyError, json.JSONDecodeError) as e:
            print(f"解析响应出错: {e}")
            retries += 1
            print(f"进行第 {retries} 次重试，将在 {retry_delay} 秒后重试...")
            time.sleep(retry_delay)
    print(f"重试 {max_retries} 次后仍翻译失败，将使用原文。")
    return text

def generate_html(translated_articles, trend_time, translated_trends):
    trend_time_str = trend_time.strftime("%Y-%m-%d %H:%M")
    trend_date_title = trend_time.strftime("%Y年%m月%d日%H时%M分")
    output_dir = f"docs"
    os.makedirs(output_dir, exist_ok=True)
    index_html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>今日谷歌热搜</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"/>
        <style>
            body {{
                background-image: url("https://ipgeo-bingpic.hf.space");
                background-size: cover;
                background-repeat: no-repeat;
                background-position: center;
                background-attachment: fixed;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: flex-start;
                min-height: 100vh;
                margin: 0;
                padding: 0;
                color: #fff;
                overflow-x: hidden;
            }}
            .header {{
                text-align: center;
                width: 100%;
                padding: 20px 0;
                background-color: rgba(0, 0, 0, 0.7);
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            }}
            h1 {{
                font-size: 2.5em;
                margin: 0;
                color: #fff;
                animation: bounceInDown;
                animation-duration: 1s;
            }}
            .subtitle {{
                font-size: 1em;
                color: #ccc;
                margin-top: 5px;
            }}
            .container {{
                width: 80%;
                max-width: 900px;
                margin: 20px auto;
                background-color: rgba(0, 0, 0, 0.7);
                border-radius: 10px;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
                padding: 20px;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                animation: fadeIn;
                animation-duration: 1s;
            }}
            .article-card {{
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 20px;
                transition: transform 0.3s ease, box-shadow 0.3s ease;
                color: #fff;
                text-decoration: none;
                display: block;
            }}
            .article-card:hover {{
                transform: translateY(-5px);
                box-shadow: 0 6px 12px rgba(0, 0, 0, 0.4);
            }}
            .article-title {{
                font-size: 1.3em;
                margin-bottom: 10px;
                color: #fff;
            }}
            .article-link {{
                color: #4CAF50;
                text-decoration: none;
                font-weight: bold;
            }}
            .article-link:hover {{
                text-decoration: underline;
            }}
            .footer {{
                text-align: center;
                font-size: 0.9em;
                color: #ccc;
                padding: 10px;
                background: rgba(0, 0, 0, 0.6);
                width: 100%;
                margin-top: 20px;
            }}
            .footer a {{
                color: #ccc;
                text-decoration: none;
            }}
            .footer a:hover {{
                color: #e0e0e0;
                text-decoration: underline;
            }}
            @media (max-width: 768px) {{
                .container {{
                    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                }}
                .article-card {{
                    padding: 15px;
                }}
                .article-title {{
                    font-size: 1.1em;
                }}
                h1 {{
                    font-size: 2em;
                }}
                .header, .footer {{
                    padding: 10px 0;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>今日谷歌热搜</h1>
            <p class="subtitle">更新时间: {trend_time_str}</p>
        </div>
        <div class="container">
    """

    for i, (trend, articles) in enumerate(translated_articles.items()):
        trend_filename = translated_trends[i].replace(" ", "_") + ".html"
        trend_filepath = os.path.join(output_dir, trend_filename)
        card_html = f"""
            <a href="{trend_filename}" class="article-card animate__animated animate__fadeInUp">
                <h2 class="article-title">{translated_trends[i]}</h2>
            </a>
        """
        index_html_content += card_html

        with open(trend_filepath, "w", encoding="utf-8") as f:
            f.write(f"""
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{translated_trends[i]}</title>
                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"/>
                <style>
                    body {{
                        background-image: url("https://ipgeo-bingpic.hf.space");
                        background-size: cover;
                        background-repeat: no-repeat;
                        background-position: center;
                        background-attachment: fixed;
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: flex-start;
                        min-height: 100vh;
                        margin: 0;
                        padding: 0;
                        color: #fff;
                        overflow-x: hidden;
                    }}
                    .header {{
                        text-align: center;
                        width: 100%;
                        padding: 20px 0;
                        background-color: rgba(0, 0, 0, 0.7);
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
                    }}
                    h1 {{
                        font-size: 2.5em;
                        margin: 0;
                        color: #fff;
                        animation: bounceInDown;
                        animation-duration: 1s;
                    }}
                    .subtitle {{
                        font-size: 1em;
                        color: #ccc;
                        margin-top: 5px;
                    }}
                    .container {{
                        width: 80%;
                        max-width: 900px;
                        margin: 20px auto;
                        background-color: rgba(0, 0, 0, 0.7);
                        border-radius: 10px;
                        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
                        padding: 20px;
                        animation: fadeIn;
                        animation-duration: 1s;
                    }}
                    .article-title {{
                        font-size: 1.5em;
                        margin-bottom: 10px;
                        color: #fff;
                    }}
                    .article-content {{
                        font-size: 1em;
                        line-height: 1.6;
                        color: #ccc;
                        margin-bottom: 20px;
                    }}
                    .article-link {{
                        color: #4CAF50;
                        text-decoration: none;
                        font-weight: bold;
                    }}
                    .article-link:hover {{
                        text-decoration: underline;
                    }}
                    .footer {{
                        text-align: center;
                        font-size: 0.9em;
                        color: #ccc;
                        padding: 10px;
                        background: rgba(0, 0, 0, 0.6);
                        width: 100%;
                        margin-top: 20px;
                    }}
                    .footer a {{
                        color: #ccc;
                        text-decoration: none;
                    }}
                    .footer a:hover {{
                        color: #e0e0e0;
                        text-decoration: underline;
                    }}
                    @media (max-width: 768px) {{
                        .container {{
                            padding: 15px;
                        }}
                        h1 {{
                            font-size: 2em;
                        }}
                        .header, .footer {{
                            padding: 10px 0;
                        }}
                        .article-title {{
                            font-size: 1.3em;
                        }}
                        .article-content {{
                            font-size: 0.9em;
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>{translated_trends[i]}</h1>
                    <p class="subtitle">更新时间: {trend_time_str}</p>
                </div>
                <div class="container">
            """)
            for article in articles:
                f.write(f"""
                <h2 class="article-title">{article['title']}</h2>
                <p class="article-content">{article['content']}</p>
                <p><a href="{article['url']}" target="_blank" class="article-link">原文链接</a></p>
                <hr>
                """)
            f.write(f"""
                </div>
                <div class="footer">
                    <span>Copyright ©<span id="year"></span> <a href="/">今日谷歌热搜</a></span> |
                    <span><a href="https://linux.do/u/f-droid" target="_blank" rel="nofollow">Powered by F-droid</a></span>
                </div>
                <script>
                    document.getElementById("year").textContent = new Date().getFullYear();
                </script>
            </body>
            </html>
            """)
    index_html_content += f"""
        </div>
        <div class="footer">
            <span>Copyright ©<span id="year"></span> <a href="">今日谷歌热搜</a></span> |
            <span><a href="https://linux.do/u/f-droid" target="_blank" rel="nofollow">Powered by F-droid</a></span>
        </div>
        <script>
            document.getElementById("year").textContent = new Date().getFullYear();
        </script>
    </body>
    </html>
    """
    with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html_content)

    markdown_filename = f"{trend_date_title}谷歌热搜.md"
    markdown_filepath = os.path.join(output_dir, markdown_filename)

    with open(markdown_filepath, "w", encoding="utf-8") as f:
        f.write(f"# {trend_date_title}谷歌热搜\n\n")
        for i, (trend, articles) in enumerate(translated_articles.items()):
            f.write(f"## {translated_trends[i]}\n\n")
            for article in articles:
                f.write(f"### [{article['title']}]({article['url']})\n\n")
                f.write(f"{article['content']}\n\n")

    return markdown_filename

def update_readme():
    readme_path = "README.md"
    archives_dir = "docs"
    markdown_files = []

    for filename in os.listdir(archives_dir):
        if filename.endswith(".md") and filename != "README.md":
            markdown_files.append(filename)

    markdown_files.sort(reverse=True)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("# 每日谷歌热搜归档\n\n")
        for filename in markdown_files:
            file_date = filename.replace("谷歌热搜.md", "")
            link = f"docs/{filename}"
            f.write(f"- [{file_date}]({link})\n")

if __name__ == "__main__":
    beijing_tz = pytz.timezone('Asia/Shanghai')
    current_time = datetime.now(beijing_tz)
    trends = get_trends()
    with open("trends.txt", "w") as f:
        for trend in trends:
            f.write(trend + "\n")
    print(f"获取到 {len(trends)} 个热搜关键词，已保存到 trends.txt")
    with open("trends.txt", "r") as f:
        trends = [line.strip() for line in f]
    all_articles = {}
    for trend in trends:
        articles = search_and_scrape(trend)
        all_articles[trend] = articles
    formatted_time_prefix = current_time.strftime("%Y-%m-%d_%H-%M")
    articles_file = f"{formatted_time_prefix}_articles.json"
    with open(articles_file, "w") as f:
        json.dump({"trends": all_articles, "datetime": current_time.isoformat()}, f, ensure_ascii=False, indent=4)
    print(f"已将所有文章保存到 {articles_file}")

    with open(articles_file, "r") as f:
        data = json.load(f)
        articles_data = data["trends"]
        trend_time_str = data["datetime"]

    trend_time = datetime.fromisoformat(trend_time_str)
    translated_articles = {}
    translated_trends = []

    for trend in trends:
        print(f"正在翻译: {trend}...")
        translated_trend = translate(trend)
        translated_trends.append(translated_trend)

    for trend, articles in articles_data.items():
        translated_articles[trend] = []
        for article in articles:
            print(f"正在翻译: {article['title']}...")
            translated_content = translate(article["content"])
            translated_articles[trend].append({
                "title": article['title'],
                "content": translated_content,
                "url": article["url"]
            })

    markdown_filename = generate_html(translated_articles, trend_time, translated_trends)
    print(f"HTML 页面和 Markdown 文件已生成到 docs 文件夹: {markdown_filename}")

    update_readme()
    print("README.md 已更新")
