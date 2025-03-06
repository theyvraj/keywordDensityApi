from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .internal_links import crawl_internal_links
import json

@csrf_exempt
@require_http_methods(["POST"])
def crawl_links(request):
    try:
        data = json.loads(request.body)
        start_url = data.get('start_url')
        max_links = data.get('max_links', 100)
        max_threads = data.get('max_threads', 5)

        if not start_url:
            return JsonResponse({'error': 'Start URL is required'}, status=400)

        internal_links = crawl_internal_links(start_url, max_links, max_threads)
        return JsonResponse({"internal links" : internal_links})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)