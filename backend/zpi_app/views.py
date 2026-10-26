from django.http import JsonResponse

from full_analysis.test_script import skibidi


def analysis_test(request):
    """Run the encoder test pipeline and return its result as JSON."""
    return JsonResponse(skibidi().model_dump())
