def print_separation(heading):
    print("\n=========================================================")
    print(heading)
    print("=========================================================\n")


def display_news_article(article_data):
    # Extract the main content dictionary
    content = article_data.get("content", {})

    title = content.get("title", "N/A")
    summary = content.get("summary", "No summary available.")
    pub_date = content.get("pubDate", "N/A")
    provider = content.get("provider", {}).get("displayName", "Unknown")
    url = content.get("canonicalUrl", {}).get("url", "N/A")

    # Clean up summary: remove trailing characters like [\u2026]
    clean_summary = summary.replace("[\u2026]", "...")

    print(f"\nTITLE: {title.upper()}")
    print(f"SOURCE: {provider} | DATE: {pub_date}")
    print("-" * 50)
    print(f"SUMMARY: {clean_summary}")
    print(f"LINK: {url}")
    print("-" * 50)
