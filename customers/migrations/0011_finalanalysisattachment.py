from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0010_statuscontrol_trading_reject_reason'),
    ]

    operations = [
        migrations.CreateModel(
            name='FinalAnalysisAttachment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='final_analysis/', verbose_name='Final Analysis File')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='Notes')),
                ('approved', models.BooleanField(default=False, verbose_name='Approved')),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='final_analysis_approved', to=settings.AUTH_USER_MODEL, verbose_name='Approved By')),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='final_analysis_uploaded', to=settings.AUTH_USER_MODEL, verbose_name='Uploaded By')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='final_analysis_attachments', to='customers.company', verbose_name='Company')),
            ],
            options={
                'verbose_name': 'Final Analysis Attachment',
                'verbose_name_plural': 'Final Analysis Attachments',
                'ordering': ['-uploaded_at'],
            },
        ),
    ]

