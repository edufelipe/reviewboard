from datetime import datetime
import logging

from django.db import models
from django.utils.translation import ugettext_lazy as _
from djblets.util.db import ConcurrencyManager

from reviewboard.policy.expression import create_expression


class Policy(models.Model):
    """
    A user configurable expression that determines the validity of an action.

    Actions represents virtually anything that a user can do on Review Board.
    A policy enables administrators to enforce rules on users.
    """

    CLOSE_REVIEW = 'close_review'
    CLOSE_REVIEW_AS_SUBMITTED = 'close_review_as_submitted'
    CLOSE_REVIEW_AS_DISCARDED = 'close_review_as_discarted'
    REOPEN_REVIEW = 'reopen_review'

    ACTIONS = (
        (CLOSE_REVIEW, _("Close review")),
        (CLOSE_REVIEW_AS_SUBMITTED, _("Close review as submitted")),
        (CLOSE_REVIEW_AS_DISCARDED, _("Close review as discarded")),
        (REOPEN_REVIEW, _("Reopen review")),
    )

    action = models.CharField(max_length=256, choices=ACTIONS, default=ACTIONS[0])

    expected_result = models.BooleanField(
        default=True,
        verbose_name=_("positive evaluation"),
        help_text=_("Indicates whether the result of the evaluation of this "
                    "policy should be true or false."))

    expression = models.TextField(
        _("expression"),
        # TODO: Write the documentation for syntax of the expression.
        help_text=_("Please refer to the manual for syntax of the expression."))

    timestamp = models.DateTimeField(_('last update'), default=datetime.now)

    # Set this up with a ConcurrencyManager to help prevent race conditions.
    objects = ConcurrencyManager()

    def __unicode__(self):
        return u"%s policy number: %i" % (self.action, self.id)

    def save(self, **kwargs):
        self.timestamp = datetime.now()

        super(Policy, self).save(**kwargs)


    def applies(self, **context):
        expression = create_expression(self.expression)
        try:
            result = expression.resolve(context)
            return result == self.expected_result
        except Exception, e:
            logging.error("Expression for policy id %i failed with message %s"
                          % (self.id, e))
            return False

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = _("policies")


