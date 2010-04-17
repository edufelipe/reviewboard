from django.contrib import admin
from django.utils.translation import ugettext_lazy as _

from reviewboard.policy.models import Policy


class PolicyAdmin(admin.ModelAdmin):
    def expression_preview(obj):
        if len(obj.expression) > 100:
            return "%s ..." % obj.expression.replace('\n', ' ')[:100]
        else:
            return obj.expression.replace('\n', ' ')
    expression_preview.short_description = 'Expression'

    list_display = ('action', expression_preview)
    fieldsets = (
        (_('Policy Information'), {
            'fields': ('action', "expression", "expected_result"),
            'classes': ('wide',),
        }),
    )


admin.site.register(Policy, PolicyAdmin)

