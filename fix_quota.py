import re

with open('app/api/v1/profile.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add func import if not present
if 'from sqlalchemy.sql import func' not in content:
    content = content.replace('from sqlalchemy.orm import Session', 'from sqlalchemy.orm import Session\nfrom sqlalchemy.sql import func')

old_stats = '''    total_meetings = db.query(Meeting).filter(Meeting.user_id == current_user.id).count()
    total_recordings = db.query(Recording).join(Meeting).filter(Meeting.user_id == current_user.id).count()
    total_transcripts = db.query(Transcript).join(Recording).join(Meeting).filter(Meeting.user_id == current_user.id).count()
    total_summaries = db.query(Summary).join(Meeting).filter(Meeting.user_id == current_user.id).count()'''

new_stats = '''    total_meetings = db.query(Meeting).filter(Meeting.user_id == current_user.id).count()
    total_recordings = db.query(Recording).join(Meeting).filter(Meeting.user_id == current_user.id).count()
    total_transcripts = db.query(Transcript).join(Recording).join(Meeting).filter(Meeting.user_id == current_user.id).count()
    total_summaries = db.query(Summary).join(Meeting).filter(Meeting.user_id == current_user.id).count()

    used_duration_minutes = db.query(
        func.coalesce(func.sum(Meeting.duration), 0)
    ).filter(Meeting.user_id == current_user.id).scalar()'''

content = content.replace(old_stats, new_stats)

content = content.replace(
    '"usedQuota": current_user.used_quota or 0,',
    '"usedQuota": int(used_duration_minutes),'
)

with open('app/api/v1/profile.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated profile.py stats calculation')
