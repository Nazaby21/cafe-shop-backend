import urllib.request
req = urllib.request.Request('http://localhost:8002/category', data=b'{\"name\":\"Test\"}', headers={'Content-Type': 'application/json'}, method='POST')
print(urllib.request.urlopen(req).read().decode())
