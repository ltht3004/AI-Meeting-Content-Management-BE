import re

with open('app/schemas/user.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'used_quota: int\n    created_at: datetime',
    'used_quota: int\n    reset_date: Optional[datetime] = None\n    created_at: datetime'
)

with open('app/schemas/user.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated user schema')
