from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .internal_links import crawl_website
import json

@csrf_exempt
def crawl_website_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        start_url = data.get('start_url')
        if not start_url:
            return JsonResponse({'error': 'start_url is required'}, status=400)
        
        sitemap = crawl_website(start_url)
        return JsonResponse({'interal links': list(sitemap)}, status=200)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)