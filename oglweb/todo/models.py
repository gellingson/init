from django.db import models

from django.utils import timezone

# Create your models here.

class User(models.Model):
    username = models.CharField(max_length=20)
    full_name = models.CharField(max_length=100)
    email = models.CharField(max_length=100)

    def __str__(self):
        return '{} ({}, {})'.format(self.username, self.full_name, self.email)

class Tag(models.Model):
    tag = models.CharField(max_length=20)

    def __str__(self):
        return self.tag


class Item(models.Model):
    PRI_LOW = -10
    PRI_NORM = 0
    PRI_HIGH = 10
    PRIORITY_CHOICES = (
        (PRI_LOW, 'Low'),
        (PRI_NORM, 'Normal'),
        (PRI_HIGH, 'High'),
    )
    title = models.CharField(max_length=80)
    desc = models.CharField(max_length=2048, blank=True)
    creation_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateField(blank=True, null=True)
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=PRI_NORM)
    completed = models.BooleanField(default=False)
    estimate = models.IntegerField(blank=True, null=True)  # in hours
    tags = models.ManyToManyField(Tag, blank=True)
    assigned = models.ManyToManyField(User, blank=True)
    
    def __str__(self):
        return self.title

# switching to enum-like mechanism
#class ActivityType(models.Model):
#    action = models.CharField(max_length=20) # comment, complete, etc


class ItemActivity(models.Model):
    ACT_COMPLETE = 10
    ACT_COMMENT = 20
    ACT_ASSIGN = 30 # id(s) of people assigned in details?
    ACT_PRIORITIZE = 50
    ACT_EDIT = 50
    ACT_ADMINEDIT = 1000
    ACT_UNCOMPLETE = 1020
    ACT_UNASSIGN = 1030 # id(s) of people removed in details?
    ACT_UNKNOWN = 9999
    ACT_CHOICES = (
        (ACT_COMPLETE, 'Complete'),
        (ACT_COMMENT, 'Comment'),
        (ACT_ASSIGN, 'Assign'),
        (ACT_PRIORITIZE, 'Prioritize'),
        (ACT_EDIT, 'Edit'),  # title, description, completion date, estimate, tags...
        (ACT_ADMINEDIT, 'Admin Edit'),
        (ACT_UNCOMPLETE, 'Mark NOT Complete'),
        (ACT_UNASSIGN, 'Remove Assignment'),
        (ACT_UNKNOWN, 'Some other action'),
    )
    item = models.ForeignKey(Item)
    user = models.ForeignKey(User)
    action = models.IntegerField(choices=ACT_CHOICES, default=ACT_UNKNOWN)
    display = models.CharField(max_length=50) # this is how it will display
    details = models.CharField(max_length=2048) # put whatever we need to in here
    date = models.DateTimeField(default=timezone.now)

