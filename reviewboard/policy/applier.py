from reviewboard.policy.models import Policy


def policy_checks(name, user=None, review_request=None):
    policies = Policy.objects.filter(action=name)
    for policy in policies:
        if not policy.applies(user=user, review_request=review_request):
            return False
    return True


