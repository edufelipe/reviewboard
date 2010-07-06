from django_evolution.mutations import AddField
from django.db import models


MUTATIONS = [
    AddField('FileDiff', 'insert_line_count', models.IntegerField, initial=0),
    AddField('FileDiff', 'delete_line_count', models.IntegerField, initial=0),
    AddField('FileDiff', 'replace_line_count', models.IntegerField, initial=0),
]
