# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Item',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=80)),
                ('desc', models.CharField(max_length=2048, blank=True)),
                ('creation_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('due_date', models.DateField(null=True, blank=True)),
                ('priority', models.IntegerField(choices=[(-10, 'Low'), (0, 'Normal'), (10, 'High')], default=0)),
                ('completed', models.BooleanField(default=False)),
                ('estimate', models.IntegerField(null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ItemActivity',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.IntegerField(choices=[(10, 'Complete'), (20, 'Comment'), (30, 'Assign'), (50, 'Prioritize'), (50, 'Edit'), (1000, 'Admin Edit'), (1020, 'Mark NOT Complete'), (1030, 'Remove Assignment'), (9999, 'Some other action')], default=9999)),
                ('display', models.CharField(max_length=50)),
                ('details', models.CharField(max_length=2048)),
                ('date', models.DateTimeField(default=django.utils.timezone.now)),
                ('item', models.ForeignKey(to='todo.Item')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tag', models.CharField(max_length=20)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='item',
            name='tags',
            field=models.ManyToManyField(to='todo.Tag', blank=True),
            preserve_default=True,
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(max_length=20)),
                ('full_name', models.CharField(max_length=100)),
                ('email', models.CharField(max_length=100)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='itemactivity',
            name='user',
            field=models.ForeignKey(to='todo.User'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='item',
            name='assigned',
            field=models.ManyToManyField(to='todo.User', blank=True),
            preserve_default=True,
        ),
    ]
