import re

with open('app/services/export_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix PDF description
content = content.replace(
'''    story.extend([
        _paragraph("Meeting Information", section_style),
        info_table,
        _paragraph("Description", section_style),
        _paragraph(_value(meeting_data.get("description"), "No description."), body_style),
        _paragraph("Participants", section_style),
    ])''',
'''    story.extend([
        _paragraph("Meeting Information", section_style),
        info_table,
    ])
    if meeting_data.get("description"):
        story.extend([
            _paragraph("Description", section_style),
            _paragraph(meeting_data.get("description"), body_style),
        ])
    story.append(_paragraph("Participants", section_style))'''
)

# 2. Fix PDF AI Summary & Recordings swap + AI Summary newlines
old_pdf_summary_rec = '''    story.extend([
        _paragraph("AI Summary", section_style),
        _paragraph(_value(meeting_data.get("summary"), "No summary generated yet."), body_style),
        _paragraph("Recordings", section_style),
    ])

    recordings = meeting_data.get("recordings") or []
    if recordings:
        for recording in recordings:
            story.append(_paragraph(f"- {_value(recording.get('file_name'))} ({_value(recording.get('size_label'))})", bullet_style))
    else:
        story.append(_paragraph("No recordings uploaded.", body_style))'''

new_pdf_summary_rec = '''    story.append(_paragraph("Recordings", section_style))
    recordings = meeting_data.get("recordings") or []
    if recordings:
        for recording in recordings:
            story.append(_paragraph(f"- {_value(recording.get('file_name'))} ({_value(recording.get('size_label'))})", bullet_style))
    else:
        story.append(_paragraph("No recordings uploaded.", body_style))

    story.append(_paragraph("AI Summary", section_style))
    summary_text = meeting_data.get("summary")
    if summary_text:
        for line in summary_text.split("\\n"):
            if line.strip():
                story.append(_paragraph(line, transcript_style))
            else:
                story.append(Spacer(1, 10))
    else:
        story.append(_paragraph("No summary generated yet.", body_style))'''

content = content.replace(old_pdf_summary_rec, new_pdf_summary_rec)

# 3. Fix DOCX description
old_docx_desc = '''    add_section("Description")
    add_body(_value(meeting_data.get("description"), "No description."))'''
new_docx_desc = '''    if meeting_data.get("description"):
        add_section("Description")
        add_body(meeting_data.get("description"))'''
content = content.replace(old_docx_desc, new_docx_desc)

# 4. Fix DOCX AI Summary & Recordings swap + AI Summary newlines
old_docx_summary_rec = '''    add_section("AI Summary")
    add_body(_value(meeting_data.get("summary"), "No summary generated yet."))

    add_section("Recordings")
    recordings = meeting_data.get("recordings") or []
    if recordings:
        for recording in recordings:
            add_bullet(
                f"{_value(recording.get('file_name'))} ({_value(recording.get('size_label'))})",
            )
    else:
        add_body("No recordings uploaded.")'''

new_docx_summary_rec = '''    add_section("Recordings")
    recordings = meeting_data.get("recordings") or []
    if recordings:
        for recording in recordings:
            add_bullet(
                f"{_value(recording.get('file_name'))} ({_value(recording.get('size_label'))})",
            )
    else:
        add_body("No recordings uploaded.")

    add_section("AI Summary")
    summary_text = meeting_data.get("summary")
    if summary_text:
        for line in summary_text.split("\\n"):
            if line.strip():
                add_transcript_body(line)
    else:
        add_body("No summary generated yet.")'''

content = content.replace(old_docx_summary_rec, new_docx_summary_rec)

with open('app/services/export_service.py', 'w', encoding='utf-8') as f:
    f.write(content)
