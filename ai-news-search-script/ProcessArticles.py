import os
import json
import requests
from azure.storage.blob import BlobServiceClient
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
TEXT_ANALYTICS_KEY = os.getenv("TEXT_ANALYTICS_KEY")
TEXT_ANALYTICS_ENDPOINT = os.getenv("TEXT_ANALYTICS_ENDPOINT")
BING_SEARCH_API_KEY = os.getenv("BING_SEARCH_API_KEY")

DEMOCRAT_KEYWORDS = [
    "Biden", "Harris", "Obama", "Clinton", "Pelosi", "Sanders", "Schumer", "AOC", "Warren", "Kamala",
    "Democrat", "Democratic", "DNC", "Liberal", "Progressive", "Left-wing",
    "Affordable Care Act", "Obamacare", "Climate change", "Green New Deal", "Gun control",
    "Minimum wage", "Medicare for All", "Immigration reform", "Social justice", "Voting rights",
    "Income inequality", "Wealth tax", "Social safety net", "Public education", "Environmental protection",
    "LGBTQ rights", "Women's rights", "Reproductive rights", "Universal healthcare", "Racial equality",
    "Social justice", "Racial equality", "Climate crisis", "Economic justice", "Healthcare access",
    "Progressive values", "Sustainable energy", "Gun reform", "Civil rights",
    "NAACP", "ACLU", "Planned Parenthood", "Human Rights Campaign", "Sierra Club", "MoveOn.org"
]


REPUBLICAN_KEYWORDS = [
    "Trump", "Pence", "McConnell", "Cruz", "Rubio", "Romney", "McCarthy", "DeSantis", "Hawley", "JD Vance", "Project 2025",
    "Republican", "GOP", "Conservative", "Right-wing", "RNC",
    "Tax cuts", "Second Amendment", "Gun rights", "Pro-life", "Border security", "Immigration enforcement",
    "Deregulation", "Small government", "Fiscal responsibility", "Lower taxes", "Healthcare reform",
    "Energy independence", "Free market", "Religious freedom", "Traditional values", "Law and order",
    "School choice", "Charter schools", "Military strength", "Veterans", "Job creation", "Economic growth",
    "Patriotism", "American values", "Family values", "National security", "Economic freedom",
    "Limited government", "Personal responsibility", "Individual liberties",
    "NRA", "Heritage Foundation", "Americans for Prosperity", "Federalist Society", "Tea Party", "Freedom Caucus"
]

def fetch_news_articles(query, count=50):
    url = "https://api.bing.microsoft.com/v7.0/news/search"
    headers = {"Ocp-Apim-Subscription-Key": BING_SEARCH_API_KEY}
    params = {
        "q": query,
        "count": count,
        "mkt": "en-US",
        "freshness": "Day",
        "category": "Politics"
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json().get("value", [])

def store_articles_in_blob(articles):
    # Connect to Blob Storage
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client('articles')

    # Store each article as a blob
    for i, article in enumerate(articles):
        blob_client = container_client.get_blob_client(f'article_{i}.json')
        blob_client.upload_blob(json.dumps(article), overwrite=True)

def read_articles_from_blob():
    # Connect to Blob Storage
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client('articles')

    # Read blobs from Blob Storage
    articles = []
    blob_list = container_client.list_blobs()
    for blob in blob_list:
        blob_client = container_client.get_blob_client(blob)
        articles.append(json.loads(blob_client.download_blob().readall().decode('utf-8')))
    return articles

def analyze_bias_and_sentiment(articles, client):
    results = []
    for article in articles:
        description = article['description']
        key_phrases = client.extract_key_phrases([description])[0].key_phrases

        democrat_score = sum(1 for phrase in key_phrases if any(keyword in phrase for keyword in DEMOCRAT_KEYWORDS))
        republican_score = sum(1 for phrase in key_phrases if any(keyword in phrase for keyword in REPUBLICAN_KEYWORDS))

        # Determine initial bias
        if democrat_score >= republican_score:
            bias = "Democrat"
        else:
            bias = "Republican"

        # Perform sentiment analysis
        sentiment_response = client.analyze_sentiment([description])[0]
        sentiment = sentiment_response.sentiment

        # If the sentiment is negative, flip the bias
        if sentiment == "negative":
            bias = "Republican" if bias == "Democrat" else "Democrat"

        results.append((article['name'], bias, sentiment))
    return results

def main():
    # Fetch recent political news articles
    query = "politics"
    articles = fetch_news_articles(query)

    # Store articles in Azure Blob Storage
    store_articles_in_blob(articles)

    # Authenticate to Text Analytics service
    client = authenticate_client()

    # Read articles from Azure Blob Storage
    stored_articles = read_articles_from_blob()

    # Perform bias and sentiment analysis
    results = analyze_bias_and_sentiment(stored_articles, client)

    # Print the results
    for i, (title, bias, sentiment) in enumerate(results):
        print(f"Article {i + 1}. [Bias:{bias}, Sentiment: {sentiment}]: {title}")

def authenticate_client():
    ta_credential = AzureKeyCredential(TEXT_ANALYTICS_KEY)
    text_analytics_client = TextAnalyticsClient(
        endpoint=TEXT_ANALYTICS_ENDPOINT, 
        credential=ta_credential)
    return text_analytics_client

if __name__ == "__main__":
    main()
