from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .url_processor import takeUrl

class URLProcessingView(APIView):
    def post(self, request, *args, **kwargs):
        url = request.data.get('url')
        if url:
            processor = takeUrl()
            result = processor.process_url(url)
            return Response(result, status=status.HTTP_200_OK)
        return Response({"error": "URL parameter is required"}, status=status.HTTP_400_BAD_REQUEST)