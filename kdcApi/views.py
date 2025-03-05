from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .url_processor import OptimizedUrlProcessor
import json

processor = OptimizedUrlProcessor()

@csrf_exempt
@require_http_methods(["POST"])
def process_url(request):
    try:
        data = json.loads(request.body)
        url = data.get('url')
        if not url:
            return JsonResponse({'error': 'URL is required'}, status=400)
        
        result = processor.process_url(url)
        return JsonResponse(result)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

@csrf_exempt
@require_http_methods(["POST"])
def process_multiple_urls(request):
    try:
        data = json.loads(request.body)
        urls = data.get('urls')
        if not urls:
            return JsonResponse({'error': 'URLs are required'}, status=400)
        
        results = processor.process_multiple_urls(urls)
        return JsonResponse(results, safe=False)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)