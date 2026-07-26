import re

with open('app/services/export_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix spacing in PDF styles
content = content.replace('spaceAfter=8,', 'spaceAfter=4,')
# Make sure body_style gets spaceBefore=2
if 'spaceBefore=2' not in content:
    content = content.replace(
        'textColor=colors.HexColor("#1f2937"),\n    )',
        'textColor=colors.HexColor("#1f2937"),\n        spaceBefore=2,\n    )'
    )
if 'firstLineIndent=-8,\n    )' in content:
    content = content.replace(
        'firstLineIndent=-8,\n    )',
        'firstLineIndent=-8,\n        spaceBefore=2,\n    )'
    )

# Fix Description condition for PDF
content = content.replace(
    'if meeting_data.get("description"):',
    'if meeting_data.get("description") and str(meeting_data.get("description")).strip():'
)

# Fix AI summary PDF Spacer
content = content.replace(
    'Spacer(1, 10)',
    'Spacer(1, 6)'
)

with open('app/services/export_service.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
