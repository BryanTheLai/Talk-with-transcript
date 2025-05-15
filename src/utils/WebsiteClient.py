
import requests
base_url = 'https://r.jina.ai/'
search_url = 'https://www.paulgraham.com/articles.html'
url = f'{base_url}{search_url}'

headers = {
    'X-Engine': 'direct',
    'X-With-Links-Summary': 'true'
}

response = requests.get(url, headers=headers)

print(response.text)
