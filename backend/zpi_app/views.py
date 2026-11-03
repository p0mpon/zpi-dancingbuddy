from django.http import JsonResponse

from full_analysis.test_script import skibidi, test_comparator


def analysis_test(request):
    """Run the encoder test pipeline and return its result as JSON."""
    return JsonResponse(skibidi().model_dump())

def comparator_test(request):
    """Run the comparator test pipeline and return its result as JSON."""
    scores, final_score = test_comparator()
    return JsonResponse({"scores": [score.model_dump() for score in scores], "final_score": final_score})